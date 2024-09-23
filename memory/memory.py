import sqlite3
import discord
import datetime


class DB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
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
                message TEXT
            )
        """
        )
        self.conn.commit()

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
        print('Incoming message to bot added to DB')

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
        print('Message to bot added to DB')

    # def retrieve_formatted_history(self, channel, bot_name):
    #     # Retrieve the chat history for the specified channel
    #     self.cursor.execute(
    #         """
    #         SELECT *
    #         FROM chat_history
    #         WHERE channel = ?
    #         ORDER BY timestamp ASC
    #     """,
    #         (channel,),
    #     )

    #     # Fetch all the rows
    #     rows = self.cursor.fetchall()

    #     # Initialize an empty list to store the formatted lines
    #     formatted_history = []

    #     # Loop through each row and format it
    #     for row in rows:
    #         (
    #             timestamp,
    #             sender_user,
    #             sender_nick,
    #             recipient_user,
    #             recipient_nick,
    #             private,
    #             message,
    #         ) = row

    #         # Modify sender and recipient formatting if they are equal to the bot name
    #         sender_info = (
    #             f"{sender_nick}"
    #             if sender_nick == bot_name
    #             else f"{sender_nick} ({sender_user})"
    #         )
    #         recipient_info = (
    #             f"{recipient_nick}"
    #             if recipient_nick == bot_name
    #             else f"{recipient_nick} ({recipient_user})"
    #         )
    #         if private != 1:
    #             recipient_info = f"Channel {str(channel)[-4:]}"

    #         formatted_line = (
    #             f"[{timestamp}] {sender_info} said to {recipient_info}: {message}"
    #         )

    #         # Append the formatted line to the list
    #         formatted_history.append(formatted_line)

    #     # Join the list into a multiline string with newlines
    #     return "\n".join(formatted_history)
    
    # def get_datetime_from_snowflake(self, snowflake_id):
    #     # Discord epoch: 2015-01-01T00:00:00Z (in milliseconds)
    #     discord_epoch = 1420070400000
    #     # Extract the timestamp part of the snowflake (first 42 bits)
    #     timestamp_ms = (snowflake_id >> 22) + discord_epoch
    #     # Convert to seconds and create a UTC datetime object
    #     timestamp_s = timestamp_ms / 1000
    #     utc_time = datetime.datetime.utcfromtimestamp(timestamp_s)
    #     # Format the datetime object as 'YYYY-MM-DD HH:MM:SS'
    #     formatted_time = utc_time.strftime('%Y-%m-%d %H:%M:%S')
    #     return formatted_time

    def get_formatted_chat_history(self, channel_id, guild_id, bot_name, is_dm, num_messages=10):
        # SQL query to fetch the last num_messages from the chat history
        query = """
        SELECT timestamp, sender_id, sender_nick, sender_user, recipient_nick, recipient_id, recipient_user, message
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
        
        chat_text += '[timestamp] Sender (sender_id) -> Recipient (recipient_id): message\n'
        chat_text += chat_history

        return chat_text

    def close(self):
        self.conn.close()
