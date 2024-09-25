import sqlite3
import discord
import pandas as pd


class CoreMemory:
    def __init__(self, db_path, bot_name):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.bot_name = bot_name
        self.create_tables()

    def create_tables(self):
        # Create the first table
        self.cursor.execute(
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
        self.cursor.execute(
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

        # Commit the changes to the database
        self.conn.commit()

    def get_uningested_channel_history(self, channel_id, chunk_size=100):
        """
        Count number of un-ingested messages for a specific channel and ingests them if they exceed the threshold.
        Ingestion involves updating contact_info and adding chunk to vectorizer.
        """
        # how far back to look for un-ingested messages
        history_window = chunk_size * 2
        # Step 1: Query the count of un-ingested messages for the specific channel within the last 'limit' rows ordered by timestamp
        count_query = """
        SELECT COUNT(*) FROM (
            SELECT * FROM chat_history
            WHERE ingested = FALSE AND channel = ?
            ORDER BY timestamp DESC
            LIMIT ?
        )
        """
        
        self.cursor.execute(count_query, (channel_id, history_window))
        message_count = self.cursor.fetchone()[0]

        # Step 2: Check if the number of messages exceeds the threshold
        if message_count >= chunk_size:
            # Step 3: Query actual un-ingested messages now that we know the count, still limiting to the last 'limit' rows
            query = """
            SELECT sender_id, sender_nick, sender_user, recipient_id, recipient_nick, recipient_user, channel, guild
            FROM chat_history
            WHERE ingested = FALSE AND channel = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """
            
            self.cursor.execute(query, (channel_id, message_count))
            rows = self.cursor.fetchall()

            # Step 4: Ingest the history for this channel
            if rows:  # Ensure there are rows before calling the next function
                formatted_history = self.get_formatted_chat_history(channel_id, self.bot_name, len(rows))

                # Step 5: Mark these messages as ingested in the database
                update_query = """
                UPDATE chat_history
                SET ingested = TRUE
                WHERE channel = ? AND ingested = FALSE
                AND timestamp <= (SELECT timestamp FROM chat_history WHERE channel = ? ORDER BY timestamp DESC LIMIT 1 OFFSET ?)
                """
                self.cursor.execute(update_query, (channel_id, channel_id, message_count))
                self.conn.commit()
                return formatted_history
            else:
                print(f"No un-ingested messages found for channel {channel_id}")
                return None
        else:
            print(f"Channel {channel_id} does not have enough messages (only {message_count} found).")
            return None

    def add_incoming_to_memory(self, in_message, bot_name, bot_id, received_time):
        """
        Add a received message to the chat history database.
        If not private, then recipient is the guild (server) ID.
        """
        is_dm = True if isinstance(in_message.channel, discord.DMChannel) == 1 else False
        self.cursor.execute(
            """
            INSERT INTO chat_history (sender_id, sender_nick, sender_user, recipient_id, recipient_nick,
            recipient_user, timestamp, channel, guild, is_dm, message) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                in_message.author.id,
                in_message.author.display_name,
                in_message.author.name,
                bot_id if is_dm else in_message.channel.id,
                bot_name if is_dm else 'Channel',
                bot_name if is_dm else 'Channel',
                received_time,
                in_message.channel.id,
                '' if is_dm else in_message.guild.id,
                is_dm,
                in_message.content
            ),
        )
        self.conn.commit()

    def add_outgoing_to_memory(self, out_message_content, recipient_display_name, recipient_name, recipient_id, channel_id, guild_id, bot_name, bot_id, sent_time, is_dm):
        """
        Add a received message to the chat history database.
        If not private, then recipient is the guild (server) ID.
        """
        self.cursor.execute(
            """
            INSERT INTO chat_history (sender_id, sender_nick, sender_user, recipient_id, recipient_nick,
            recipient_user, timestamp, channel, guild, is_dm, message) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bot_id,
                bot_name,
                bot_name,
                recipient_id if is_dm else channel_id,
                recipient_display_name if is_dm else 'Channel',
                recipient_name if is_dm else 'Channel',
                sent_time,
                channel_id,
                guild_id,
                is_dm,
                out_message_content
            ),
        )
        self.conn.commit()

    def get_formatted_chat_history(self, channel_id, bot_name, num_messages):
        """Retrieves LLM friendly formatted chat history for specific channel."""
        query = """
        SELECT timestamp, sender_id, sender_nick, sender_user, recipient_nick, recipient_id, recipient_user, message, is_dm, guild
        FROM chat_history
        WHERE channel = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        params = (channel_id, num_messages)

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

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
            if sender_nick != bot_name and sender_nick != '':
                unique_names.add(sender_nick)

        # Convert the unique names set to a sorted list, then join them with a comma
        unique_names_list = sorted(unique_names)
        unique_names_string = ', '.join(unique_names_list)

        # Add a check to avoid showing an empty list
        people_in_channel = unique_names_string

        # Combine the chat history and the list of people
        if is_dm:
            chat_text = f'This is the most recent Discord DM history between you and {people_in_channel} in Channel {channel_id}\n'
        else:
            chat_text = f'This is the most recent Discord chat history for Channel {channel_id} in Guild {guild_id}\n'
            chat_text += f'The people who have spoken in this channel are: {people_in_channel}\n'
        
        chat_text += '[UTC timestamp] Sender (sender_id) -> Recipient (recipient_id): message\n'
        chat_text += chat_history

        return chat_text
    
    import pandas as pd

    def create_df(self):
        '''Create a pandas DataFrame from the chat history for use externally.'''
        # Execute the query to fetch all rows from the 'chat_history' table
        self.cursor.execute("SELECT * FROM chat_history")
        rows = self.cursor.fetchall()

        # Get the column names from the cursor
        columns = [desc[0] for desc in self.cursor.description]

        # Create a pandas DataFrame from the rows and columns
        df = pd.DataFrame(rows, columns=columns)

        return df

    def close(self):
        self.conn.close()
