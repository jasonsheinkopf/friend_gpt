import sqlite3
import discord
import pandas as pd
from functools import wraps
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os

def with_connection(func):
    '''Decorator to create a new connection and cursor for each function call.'''
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Debug print for args and kwargs
        # print(f"Debug: Called {func.__name__} with args: {args}, kwargs: {kwargs}")
        # Get the instance of CoreMemory (`self`) from args
        self = args[0]
        # Create a new connection using `self.db_path`
        conn = sqlite3.connect(self.cfg.CORE_MEMORY_PATH, check_same_thread=True)  # Safe to set to True as each call is in a single thread
        cursor = conn.cursor()
        try:
            # Debug print for cursor and arguments being passed to the function
            # print(f"Debug: Passing cursor and remaining args to {func.__name__}")

            # Pass the cursor as an additional positional argument
            result = func(self, cursor, *args[1:], **kwargs)
            conn.commit()
            return result
        finally:
            # Always close the connection to avoid resource leaks
            conn.close()
            # print(f"Debug: Closed connection for {func.__name__}")

    return wrapper


class CoreMemory:
    def __init__(self, cfg, agent_name, agent_id):
        self.cfg = cfg
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.vector_model = SentenceTransformer(self.cfg.CHAT_VECTOR_EMBEDDING_MODEL)
        self.load_chat_vector_index()
        self.create_tables()

    @with_connection
    def create_tables(self, cursor):
        '''Create the tables if they do not exist.'''
        # Create the first table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                sender_nick TEXT,
                sender_user TEXT,
                recipient_id INTEGER,
                recipient_nick TEXT,
                recipient_user TEXT,
                timestamp TEXT,
                channel INTEGER,
                guild INTEGER,
                is_dm BOOLEAN,
                ingested INTEGER DEFAULT -1,
                summarized BOOLEAN DEFAULT FALSE,
                message TEXT
            )
            """
        )

        # Create the second table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_info (
                user_id INTEGER PRIMARY KEY,
                user_nick TEXT,
                user_name TEXT,
                channels TEXT, -- Store comma-separated channel IDs
                info TEXT
            )
            """
        )

    # @with_connection
    # def get_uningested_channel_history(self, cursor, chan_id, chunk_size=100):
    #     """
    #     Count number of un-ingested messages for a specific channel and ingests them if they exceed the threshold.
    #     Ingestion involves updating contact_info and adding chunk to vectorizer.
    #     """
    #     # how far back to look for un-ingested messages
    #     history_window = chunk_size * 2
    #     # Step 1: Query the count of un-ingested messages for the specific channel within the last 'limit' rows ordered by timestamp
    #     count_query = """
    #     SELECT COUNT(*) FROM (
    #         SELECT * FROM chat_history
    #         WHERE ingested = FALSE AND channel = ?
    #         ORDER BY timestamp DESC
    #         LIMIT ?
    #     )
    #     """
        
    #     cursor.execute(count_query, (chan_id, history_window))
    #     message_count = cursor.fetchone()[0]

    #     # Step 2: Check if the number of messages exceeds the threshold
    #     if message_count >= chunk_size:
    #         # Step 3: Query actual un-ingested messages now that we know the count, still limiting to the last 'limit' rows
    #         query = """
    #         SELECT sender_id, sender_nick, sender_user, recipient_id, recipient_nick, recipient_user, channel, guild
    #         FROM chat_history
    #         WHERE ingested = FALSE AND channel = ?
    #         ORDER BY timestamp DESC
    #         LIMIT ?
    #         """
            
    #         cursor.execute(query, (chan_id, message_count))
    #         rows = cursor.fetchall()

    #         # Step 4: Ingest the history for this channel
    #         if rows:  # Ensure there are rows before calling the next function
    #             long_history, short_history, _ = self.get_formatted_chat_history(chan_id, len(rows))

    #             # Step 5: Mark these messages as ingested in the database
    #             update_query = """
    #             UPDATE chat_history
    #             SET ingested = TRUE
    #             WHERE channel = ? AND ingested = FALSE
    #             AND timestamp <= (SELECT timestamp FROM chat_history WHERE channel = ? ORDER BY timestamp DESC LIMIT 1 OFFSET ?)
    #             """
    #             cursor.execute(update_query, (chan_id, chan_id, message_count))
    #             return formatted_history
    #         else:
    #             print(f"No un-ingested messages found for channel {chan_id}")
    #             return None
    #     else:
    #         print(f"Channel {chan_id} does not have enough messages (only {message_count} found).")
    #         return None

    @with_connection
    def add_incoming_to_memory(self, cursor, in_message, received_time):
        """
        Add a received message to the chat history database.
        If not private, then recipient is the guild (server) ID.
        """
        is_dm = True if isinstance(in_message.channel, discord.DMChannel) == 1 else False
        cursor.execute(
            """
            INSERT INTO chat_history (sender_id, sender_nick, sender_user, recipient_id, recipient_nick,
            recipient_user, timestamp, channel, guild, is_dm, message) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                in_message.author.id,
                in_message.author.display_name,
                in_message.author.name,
                self.agent_id if is_dm else in_message.channel.id,
                self.agent_name if is_dm else 'Channel',
                self.agent_name if is_dm else 'Channel',
                received_time,
                in_message.channel.id,
                '' if is_dm else in_message.guild.id,
                is_dm,
                in_message.content
            ),
        )

    @with_connection
    def add_outgoing_to_memory(self, cursor, msg_txt, rec_id, rec_nick, rec_user, is_dm, chan_id, guild, sent_time):
        """
        Add a received message to the chat history database.
        If not private, then recipient is the guild (server) ID.
        """
        cursor.execute(
            """
            INSERT INTO chat_history (sender_id, sender_nick, sender_user, recipient_id, recipient_nick,
            recipient_user, timestamp, channel, guild, is_dm, message) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.agent_id,
                self.agent_name,
                self.agent_name,
                rec_id if is_dm else chan_id,
                rec_nick if is_dm else 'Channel',
                rec_user if is_dm else 'Channel',
                sent_time,
                chan_id,
                guild,
                is_dm,
                msg_txt
            ),
        )

    @with_connection
    def get_recent_channel_hist(self, cursor, chan_id, num_msg):
        """
        Retrieves chat object for specific channel with recent messages.
        """
        query = """
        SELECT timestamp, sender_id, sender_nick, recipient_id, recipient_nick, message, is_dm, guild
        FROM chat_history
        WHERE channel = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        params = (chan_id, num_msg)
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Reverse the order to display the oldest message first
        rows.reverse()

        return self.format_chat_history(rows, chan_id)
    
    @with_connection
    def ingest_channel_hist_to_vector(self, cursor, chan_id):
        """
        Retrieves uningested chat history as list of sequential string chunks and stores to vector memory.
        """
        # Step 1: Check the count of un-ingested messages
        count_query = """
        SELECT COUNT(*)
        FROM chat_history
        WHERE channel = ? AND ingested = -1
        """
        cursor.execute(count_query, (chan_id,))
        count = cursor.fetchone()[0]

        # check if below threshold
        if count < self.cfg.CHAT_VECTOR_MEMORY_MIN_CHUNK_SIZE:
            return None
        
        # chunk size should like be less than max chunk size
        max_chunk_size = self.cfg.CHAT_VECTOR_MEMORY_MIN_CHUNK_SIZE * 2
        
        # try different numbers of chunks
        for num_chunks in range(1, 1000):
            # find chunk size that is less than max size
            if count // num_chunks + count % num_chunks < max_chunk_size:
                chunk_quantity = num_chunks
                break

        # create chunk indices such that the last chunk takes any leftover rows
        base_chunk_size = count // chunk_quantity
        chunk_indices = [base_chunk_size * i for i in range(chunk_quantity)]


        # Retrieve all un-ingested messages
        query = """
        SELECT id, timestamp, sender_id, sender_nick, recipient_id, recipient_nick, message, is_dm, guild
        FROM chat_history
        WHERE channel = ? AND ingested = -1
        ORDER BY timestamp DESC
        """
        cursor.execute(query, (chan_id,))
        rows = cursor.fetchall()

        # Reverse the order to display the oldest message first
        rows.reverse()

        chunk_sizes = []

        # iterate over each chunk
        for i in range(len(chunk_indices)):
            start_idx = chunk_indices[i]
            # if its the last chunk, take all remaining rows
            if i == len(chunk_indices) - 1:
                chunk = rows[start_idx:]
            else:
                end_idx = chunk_indices[i + 1]
                chunk = rows[start_idx:end_idx]

            # track chunk sizes for logging
            chunk_sizes.append(len(chunk))

            # format chunk rows to single formatted string
            chat = self.format_chat_history(chunk, chan_id)
            formatted_chunk_string = chat.formatted_long_history

            # generate chunk embeddings
            embeddings = self.vector_model.encode(formatted_chunk_string)
            embeddings = np.array(embeddings, dtype=np.float32).reshape(1, -1)

            # add embeddings to vector index
            self.chat_vector_index.add(embeddings)

            # check current index size to use as chunk locator
            index_locator = self.chat_vector_index.ntotal

            # update vector store index locator in database
            for row in chunk:
                update_query = """
                UPDATE chat_history
                SET ingested = ?
                WHERE channel = ? AND id = ?
                """
                cursor.execute(update_query, (index_locator, chan_id, row[0]))

        # write index attribute to file
        faiss.write_index(self.chat_vector_index, self.cfg.CHAT_VECTOR_MEMORY_PATH)
        print(f"Saved FAISS index to {self.cfg.CHAT_VECTOR_MEMORY_PATH}")
        # Min and max size of chunks for logging
        min_size = min(chunk_sizes)
        max_size = max(chunk_sizes)
        print(f'Added {len(chunk_sizes)} chunks of size range {min_size} to {max_size} to vector memory.')

    def load_chat_vector_index(self):
        if os.path.exists(self.cfg.CHAT_VECTOR_MEMORY_PATH):
            self.chat_vector_index = faiss.read_index(self.cfg.CHAT_VECTOR_MEMORY_PATH)
            print(f"Loaded FAISS index from {self.cfg.CHAT_VECTOR_MEMORY_PATH}")
        else:
            # self.chat_vector_index = faiss.IndexHNSWFlat(self.vector_model.get_sentence_embedding_dimension(), self.cfg.CHAT_EMBED_NEIGHBORS)
            self.chat_vector_index = faiss.IndexFlatL2(self.vector_model.get_sentence_embedding_dimension())
            print(f"Created new FAISS index")

    def chat_vector_search(self, query_text, k=1):
        """
        Search the chat vector memory for the closest k vectors to the query text.
        """
        # Ensure the query is in list format and output is in float32 format for FAISS compatibility
        query_embedding = self.vector_model.encode([query_text])  # Keep as list to match model input requirements
        print(query_embedding)
        query_embedding = np.array(query_embedding, dtype='float32')  # Convert to float32 for FAISS
        print(query_embedding)

        # Perform the search on the FAISS index
        D, I = self.chat_vector_index.search(query_embedding, k)

        # Return the distances and indices
        return D, I

    def format_chat_history(self, rows, chan_id):
        chat = ChatHistory(chan_id, self.cfg)

        for idx, row in enumerate(rows):
            idx = row[0]
            # timestamp = row[1]
            sender_id = row[2]
            sender_nick = row[3]
            recipient_id = row[4]
            recipient_nick = row[5]
            message = row[6]
            is_dm = row[7]
            guild_id = row[8]
            
            # Format the sender and recipient
            if sender_nick == self.agent_name:
                sender_id = 'Agent'
                chat.speaker_is_agent_list.append(True)
            else:
                chat.speaker_is_agent_list.append(False)
            sender = f'{sender_nick} ({sender_id})'
            if recipient_nick == self.agent_name:
                recipient_id = 'Agent'
            # recipient = f'{recipient_nick} ({recipient_id})'
            # [2024-10-01 23:31:39] User (360964041130115072) -> Friend GPT (Agent): Message
            # chat.long_history.append(f'[{timestamp}] {sender} -> {recipient}: {message}')
            chat.long_history.append(f'{sender}: {message}')

            # add list of unique senders
            if sender_nick != self.agent_name:
                chat.unique_names.add(sender_nick)

            # record last agent message index
            if sender_nick == self.agent_name:
                chat.last_agent_msg_idx = idx

            chat.is_dm = is_dm
            chat.guild_id = guild_id

        chat.process_chat_history()

        return chat
    
    @with_connection
    def get_all_chan_ids(self, cursor):
        '''Retrieve all unique channel IDs from the chat history.'''
        query = "SELECT DISTINCT channel FROM chat_history"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    
    @with_connection
    def get_channel_metadata(self, cursor, chan_id):
        '''Retrieve the recipient details for a specific channel.'''
        query = "SELECT * FROM chat_history WHERE channel = ? LIMIT 1"
        params = (chan_id,)
        cursor.execute(query, params)
        row = cursor.fetchone()

        # create df including column names
        df = pd.DataFrame([row], columns=[x[0] for x in cursor.description])

        # Determine if the agent is the recipient or sender and set recipient values accordingly
        if df['recipient_nick'].iloc[0] == self.agent_name:
            role = 'sender'
        else:
            role = 'recipient'

        # Extract recipient details
        rec_nick = df[f'{role}_nick'].iloc[0]
        rec_user = df[f'{role}_user'].iloc[0]
        rec_id = int(df[f'{role}_id'].iloc[0])
        guild = df['guild'].iloc[0]
        guild = '' if guild == '' else int(guild)
        is_dm = bool(df['is_dm'].iloc[0])

        return rec_nick, rec_user, rec_id, guild, is_dm

    @with_connection
    def create_df(self, cursor):
        '''Create a pandas DataFrame from the chat history for use externally.'''
        # Execute the query to fetch all rows from the 'chat_history' table
        cursor.execute("SELECT * FROM chat_history")
        rows = cursor.fetchall()

        # Get the column names from the cursor
        columns = [desc[0] for desc in cursor.description]

        # Create a pandas DataFrame from the rows and columns
        df = pd.DataFrame(rows, columns=columns)

        return df


class ChatHistory:
    def __init__(self, chan_id, cfg):
        self.chan_id = chan_id
        self.cfg = cfg
        self.long_history = []
        self.formatted_long_history = ''
        self.unique_names = set()
        self.is_dm = None
        self.guild_id = None
        self.speaker_is_agent_list = []

    def process_chat_history(self):
        # Convert the unique names set to a sorted list, then join them with a comma
        self.unique_names_list = sorted(list(self.unique_names))
        unique_names_string = ', '.join(self.unique_names_list)

        # Combine the chat history and the list of people
        if self.is_dm:
            chat_text = f'Private chat with {unique_names_string} in Channel {self.chan_id}\n'
        else:
            chat_text = f'Group chat with {unique_names_string} in Channel {self.chan_id}, Guild {self.guild_id}\n'
        
        # get short history which will be used as next prompt
        self.short_history = self.long_history[-self.cfg.SHORT_HISTORY_LENGTH:]

        # format histories to be LLM friendly
        self.formatted_long_history = '\n'.join(self.long_history) + '\n' + chat_text
        self.formatted_short_history = '\n'.join(self.short_history)

    def should_respond(self):
        # if last speaker was the user, then the agent should respond
        if self.speaker_is_agent_list[-1] is False:
            agent_should_respond = True
            # print('last speaker was the user', self.chan_id)
            # print(self.formatted_long_history)
        # if the second and third to last were the user, then the agent should respond
        elif len(self.speaker_is_agent_list) > 2 and self.speaker_is_agent_list[-2] == False and self.speaker_is_agent_list[-3] == False:
            # print('second and third to last speakers were the user')
            agent_should_respond = True
            # print(self.formatted_long_history)
        else:
            agent_should_respond = False

        return agent_should_respond
    