# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# import time
# import os

# # Set the path to your ChromeDriver executable
# driver_path = '/Applications/chromedriver-mac-arm64/chromedriver'
# service = Service(driver_path)

# # Set up Chrome options for user profile
# chrome_options = Options()
# user_data_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome/WhatsAppSelenium')
# chrome_options.add_argument(f'user-data-dir={user_data_dir}')

# def load_whatsapp():
#     print("Starting ChromeDriver and opening WhatsApp Web...")
#     driver = webdriver.Chrome(service=service, options=chrome_options)
#     driver.get("https://web.whatsapp.com/")
    
#     wait = WebDriverWait(driver, 60)  # Increased wait time to 60 seconds
#     try:
#         # Wait until the search box is visible
#         wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')))
#         print("WhatsApp Web loaded successfully.")
#     except TimeoutException:
#         print("Timeout waiting for WhatsApp to load. You may need to scan the QR code.")
#         input("Press Enter after scanning the QR code or when WhatsApp is loaded...")
    
#     return driver

# def send_message(driver, contact_name, message):
#     print(f"Attempting to send message to {contact_name}...")
#     wait = WebDriverWait(driver, 60)  # 60 seconds wait time

#     try:
#         # Wait for the search box to be visible
#         print("Waiting for the search box to be visible...")
#         search_box = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')))
        
#         # Search for the contact
#         print(f"Searching for contact: {contact_name}")
#         search_box.clear()
#         search_box.send_keys(contact_name)
#         time.sleep(2)
        
#         # Select the chat with the contact
#         print(f"Selecting the contact: {contact_name}")
#         contact = wait.until(EC.element_to_be_clickable((By.XPATH, f'//span[@title="{contact_name}"]')))
#         contact.click()
#         time.sleep(2)

#         # Find the message box
#         print("Finding the message input box...")
#         message_box = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')))
#         message_box.click()
        
#         # Send the message
#         print(f"Sending message: {message}")
#         message_box.send_keys(message)
#         message_box.send_keys(Keys.RETURN)
#         time.sleep(2)
#         print("Message sent successfully!")
    
#     except TimeoutException as e:
#         print(f"Timeout occurred: {e}")
#     except NoSuchElementException as e:
#         print(f"Element not found: {e}")
#     except Exception as e:
#         print(f"An error occurred: {e}")

# def main():
#     print("Running the main function...")
#     driver = load_whatsapp()
    
#     contact_name = "Jason Sheinkopf"  # Replace with the contact name you want to message
#     message = "Hello from Selenium!"
    
#     send_message(driver, contact_name, message)

#     print("Closing the browser in 5 seconds...")
#     time.sleep(5)
#     driver.quit()
#     print("Browser closed.")

# if __name__ == "__main__":
#     main()