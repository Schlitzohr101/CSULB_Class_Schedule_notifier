import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from twilio.rest import Client
import os
import threading
import time


def get_current_year():
    current_year = datetime.now().year
    return current_year

def check_if_integer_and_valid(x,min,max):
    try:
        int_value = int(x)
        return (int_value >= min and int_value <= max)
    except ValueError:
        return False

def yes_or_no_checker(user_input):
    valid_yes = {"yes", "y", "YES", "Y", "ye", "YE"}
    valid_no = {"no", "n", "nope","NO","N","NOPE"}

    while True: 
        if user_input in valid_yes:

            return True
        elif user_input in valid_no:
            return False
        else:
            print("Invalid input, please enter 'yes' or 'no'.")
            

def get_request(url):
    # url = 'https://www.csulb.edu/student-records/schedule-of-classes'
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        content = response.content   # Get the content of the response
        return content
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"
    
def soup_maker(content):
    return BeautifulSoup(content, 'html.parser') 
    
# def html_formater(content):
#     soup = BeautifulSoup(content, 'html.parser')
#     return soup.prettify()


def get_semesters_available(content):
    soup_content = soup_maker(content=content)
    buttons = soup_content.find_all('button', {
            'type': 'button',
            'data-toggle': 'collapse',
            'aria-expanded': 'false',
            'class': 'collapsed'
        })
    
    if buttons:
            print( "found semesters available...")
    else:
            print("no buttons found... exiting")
            return None
    
    semesters = []
    for button in buttons:
        button_text = button.get_text(strip=True)
        if "Courses" in button_text:
            semesters.append(button_text.replace("Courses", ""))
            print(str(len(semesters)) + " " + button_text)
            
    
    return semesters
        
def get_subjects_for_semester(semester_soup):
    
    div = semester_soup.find('div', class_='indexList')
    
    subjects = []
    
    if div:
        uls = div.find_all('ul')
        
        for ul in uls:
            list_elements = ul.find_all('li')
            for element in list_elements:
                refs = element.find('a')
                element_tuple = ( element.text , refs.get('href') )
                subjects.append( element_tuple )
                print(str(len(subjects)) + " " + element_tuple[0])
                
    return subjects    
    
def class_close_or_openish(table_data_entry):
    dot = table_data_entry.find('div', class_="dot")
    return dot != None
        
        
def get_class_code_and_status(table_row_data):
        #want second and 9th pieces
        return ((table_row_data[0].text,class_close_or_openish(table_row_data[7])))
        

def get_classes_for_subject(subject_soup):
    
    session_div = subject_soup.find('div', class_='session')
    
    classes = []
    
    course_div = session_div.find_all('div', class_='courseBlock')
    for course in course_div:
        course_header = course.find('div', class_='courseHeader')
        span = course_header.find('span', class_='courseCode')
        class_code = span.text
        span = course_header.find('span', class_='courseTitle')
        class_title = span.text
        print(class_code + " " + class_title)
        
        course_sections = course.find('table', class_='sectionTable')
        count = 0
        for row in course_sections.find_all('tr'):
            if count == 0:
                count += 1
                continue
            data = row.find_all('td')
            class_tuple = get_class_code_and_status(data)
            classes.append(class_tuple)
            print(str(len(classes))+'\t'+ class_tuple[0] + " is open? "+str(class_tuple[1]))
            
    return classes
    
    
        
def print_all_tags(content):
    for tag in soup_maker(content=content).find_all(True):
        print(tag.name)

def get_url_for_Semester(soup, semester):
    year = get_current_year()
    links = soup.find_all('a', string=semester+str(year))

        # Extract the href attribute of each link
    hrefs = [link.get('href') for link in links if link.get('href')]
    return hrefs[0]

def send_textbelt_sms(phone_number, message):
    url = 'https://textbelt.com/text'
    api_key = os.getenv('TEXTBELT_API_KEY')
    payload = {
        'phone': phone_number,
        'message': message,
        'key': api_key  # Use 'textbelt' for free tier, for paid you will use your API key
    }

    response = requests.post(url, data=payload)
    result = response.json()
    if result['success']:
        print('Message sent successfully')
    else:
        print('Failed to send message:', result['error'])

def find_and_send_text_upon_open_status_for_class(classes_to_track, subject_soup):
    session_div = subject_soup.find('div', class_='session')
    course_div = session_div.find_all('div', class_='courseBlock')
    prev_printed_course_code = 0
    for class_tuple in classes_to_track: #classes_to_track contains tuples -> ('4850', False)
        for course in course_div:
            course_header = course.find('div', class_='courseHeader')
            span = course_header.find('span', class_='courseCode')
            course_sections = course.find('table', class_='sectionTable')
            count = 0
            for row in course_sections.find_all('tr'):
                if count == 0:
                    count += 1
                    continue
                data = row.find_all('td')
                temp_class_tuple = get_class_code_and_status(data)
                if temp_class_tuple[0] == class_tuple[0]:
                    if prev_printed_course_code != span.text:
                        class_code = span.text
                        span = course_header.find('span', class_='courseTitle')
                        class_title = span.text
                        print(class_code + " " + class_title)
                        prev_printed_course_code = class_code
                    if temp_class_tuple[1] == class_tuple[1]:
                        print(f"status hasn't changed for class {class_tuple[0]}")
                    else:
                        print(f'status has changed for class {class_tuple[0]}!')
                        send_textbelt_sms(os.getenv('PHONE_NUMBER'),f"{class_tuple[0]} is now open! Go register")
              
def continuous_checkup_function(subject_url,classes_to_track):
    print("calling continuous funct")
    subject_content = get_request(subject_url)
    subject_soup = soup_maker(subject_content)
    find_and_send_text_upon_open_status_for_class(classes_to_track,subject_soup)
    threading.Timer(300, continuous_checkup_function,[subject_url,classes_to_track]).start()

# # Example usage
# phone_number = '19494698351'  # Replace with the recipient's phone number
# message = 'Hello, this is a test message from Python!'
# send_textbelt_sms(phone_number, message)          


#Semester selection block
request_content = get_request('https://www.csulb.edu/student-records/schedule-of-classes')
soup_content = soup_maker(request_content)
semester_options = get_semesters_available(request_content)
selection = 0
if semester_options != [] and len(semester_options) != 0:
    bad_input = True
    while bad_input:
        selection = input("select semester to look up subjects for\n:")
        bad_input = not check_if_integer_and_valid(selection,1,len(semester_options))
        if bad_input:
            print("Please enter a valid integer between 1 and "+str(len(semester_options)))
        else:
            selection = int(selection)
            selection -= 1


#Subject selection
selected_semester = semester_options[selection]
print(selected_semester)
semester_url = get_url_for_Semester(soup_content,selected_semester)
semester_content = get_request(semester_url)
soup_semester = soup_maker(semester_content)
subjects = get_subjects_for_semester(soup_semester)

selection = 0
if subjects != [] and len(subjects) != 0:
    bad_input = True
    while bad_input:
        selection = input("select subject to look up classes for\n:")
        bad_input = not check_if_integer_and_valid(selection,1,len(subjects))
        if bad_input:
            print("Please enter a valid integer between 1 and "+str(len(subjects)))
        else:
            selection = int(selection)
            selection -= 1

#Classes selection

selected_subject = subjects[selection]
print(selected_subject[0])
subject_url = semester_url+selected_subject[1]
subject_content = get_request(subject_url)
subject_soup = soup_maker(subject_content)

classes = get_classes_for_subject(subject_soup)
classes_to_track = []
selection = 0
if classes != [] and len(classes) != 0:
    result_okay = False
    while not result_okay:
        while True:
            selection = input("select classes to be tracked, enter \'done\' when finished\n:")
            bad_input = not check_if_integer_and_valid(selection,1,len(classes))
            if bad_input:
                if selection.upper().find("DONE") != -1:
                    break
                print("Please enter a valid integer between 1 and "+str(len(classes)))
            else:
                selection = int(selection)
                selection -= 1
                print("Adding course:"+classes[selection][0])
                classes_to_track.append(classes[selection])
                #selection needs to be added to list to track.. 
        print(classes_to_track)
        response = input("Are these the classes okay to track?\n(Y)es or (N)o:")
        result_okay = yes_or_no_checker(response)
        if not result_okay:
            response = input("clear selections?\n(Y)es or (N)o:")
            if yes_or_no_checker(response):
                classes_to_track = []

# # print(classes_to_track)
subject_url = semester_url+selected_subject[1]
# subject_content = get_request(subject_url)
# subject_soup = soup_maker(subject_content)
# find_and_send_text_upon_open_status_for_class(classes_to_track,subject_soup)
# schedule.every(5).minutes.do(continuous_checkup_function)

continuous_checkup_function(subject_url,classes_to_track)