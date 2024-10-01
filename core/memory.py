import sqlite3
import discord
import pandas as pd
from functools import wraps


def with_connection(func):
    '''Decorator to create a new connection and cursor for each function call.'''
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Debug print for args and kwargs
        # print(f"Debug: Called {func.__name__} with args: {args}, kwargs: {kwargs}")
        # Get the instance of CoreMemory (`self`) from args
        self = args[0]
        # Create a new connection using `self.db_path`
        conn = sqlite3.connect(self.db_path, check_same_thread=True)  # Safe to set to True as each call is in a single thread
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
    def __init__(self, cfg, bot_name, bot_id):
        self.db_path = cfg.CORE_MEMORY_PATH
        self.bot_name = bot_name
        self.bot_id = bot_id
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
                ingested BOOLEAN DEFAULT FALSE,
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
    #             formatted_history = self.get_formatted_chat_history(chan_id, len(rows))

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
                self.bot_id if is_dm else in_message.channel.id,
                self.bot_name if is_dm else 'Channel',
                self.bot_name if is_dm else 'Channel',
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
                self.bot_id,
                self.bot_name,
                self.bot_name,
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
    def get_formatted_chat_history(self, cursor, chan_id, num_msg):
        """Retrieves LLM friendly formatted chat history for specific channel."""
        query = """
        SELECT timestamp, sender_id, sender_nick, sender_user, recipient_nick, recipient_id, recipient_user, message, is_dm, guild
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

        # Initialize a set to store unique names (excluding bot_name)
        unique_names = set()

        chat_history = ''

        for row in rows:
            timestamp = row[0]
            sender_id = row[1]
            sender_nick = row[2]
            sender_user = row[3]
            recipient_nick = row[4]
            recipient_id = row[5]
            recipient_user = row[6]
            message = row[7]
            is_dm = row[8]
            guild_id = row[9]
            
            # Format the sender and recipient
            sender = sender_nick if sender_nick == sender_user else f'{sender_nick} ({sender_id})'
            recipient = recipient_nick if recipient_nick == recipient_user else f'{recipient_nick} ({recipient_id})'
            chat_history += f'[{timestamp}] {sender} -> {recipient}: {message}\n'

            # Add sender_nick to the unique names, but exclude bot_name
            if sender_nick != self.bot_name and sender_nick != '':
                unique_names.add(sender_nick)

        # Convert the unique names set to a sorted list, then join them with a comma
        unique_names_list = sorted(unique_names)
        unique_names_string = ', '.join(unique_names_list)

        # Add a check to avoid showing an empty list
        people_in_channel = unique_names_string

        # Combine the chat history and the list of people
        if is_dm:
            chat_text = f'This is the most recent Discord DM history between you and {people_in_channel} in Channel {chan_id}\n'
        else:
            chat_text = f'This is the most recent Discord chat history for Channel {chan_id} in Guild {guild_id}\n'
            chat_text += f'The people who have spoken in this channel are: {people_in_channel}\n'
        
        chat_text += '[UTC timestamp] Sender (sender_id) -> Recipient (recipient_id): message\n'
        chat_text += chat_history

        return chat_text
    
    @with_connection
    def get_channel_metadata(self, cursor, chan_id):
        '''Retrieve the recipient details for a specific channel.'''
        query = "SELECT * FROM chat_history WHERE channel = ? LIMIT 1"
        params = (chan_id,)
        cursor.execute(query, params)
        row = cursor.fetchone()

        # create df including column names
        df = pd.DataFrame([row], columns=[x[0] for x in cursor.description])

        # Determine if the bot is the recipient or sender and set recipient values accordingly
        if df['recipient_nick'].iloc[0] == self.bot_name:
            role = 'sender'
        else:
            role = 'recipient'

        # Extract recipient details
        rec_nick = df[f'{role}_nick'].iloc[0]
        rec_user = df[f'{role}_user'].iloc[0]
        rec_id = df[f'{role}_id'].iloc[0]
        guild = df['guild'].iloc[0]
        is_dm = df['is_dm'].iloc[0]

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
