import re
from datetime import datetime
from django.utils.crypto import get_random_string

def is_correct_format(date_string):
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except (TypeError, ValueError):
        return False


def generate_temporary_password():
    temp_password = get_random_string(
        length=12, allowed_chars="ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%"
    )

    return temp_password

def is_valid_email(email):
    
    # Regular expression for a valid email
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email))