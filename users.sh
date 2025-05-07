#!/bin/bash

# EXISTING EDGE CASES TO CONSIDER
# * What is the main source of truth for the users and groups?
#   - If the csv file is the source of truth, then we need to make sure that the users and groups
#     not in the csv file are removed from the system.
#   - If the system is the source of truth, then we need to make sure that the users and groups
#     not in the system are removed from the csv file.
# * What about the output file? Do we remove users and groups from the output file that does not exist
#   in the csv file or the system?

# DEFINE FUNCTIONS

debug-output () {
    for i in "${!arr_users[@]}"; do
        echo "------------------------"
        echo "Entry $(($i+1)):"
        echo "User: ${arr_users[$i]}"
        echo "Group: ${arr_groups[$i]}"
        echo "Password: ${arr_pass[$i]}"
    done
    echo "------------------------"
    echo " "
}

# PRE-RUN SANITY CHECKS

#check if the script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

# check if the CSV file exists
if [ ! -f users.csv ]; then
    echo "CSV file not found!"
    exit
fi

# END OF PRE-RUN SANITY CHECKS

# FiLE HANDLING CHECK

# check if output file already exists
if [ -f username.password ]; then
    echo "Output file already exists."
    echo "This file will be overwritten and new passwords generated for fresh accounts."
    echo "Do you want to overwrite it? (y/N)"
    read -r answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo "Overwriting output file..."
    else
        echo "Exiting without changes."
        exit
    fi
fi

# END OF FILE HANDLING CHECK

# RUN SCRIPT

# if output file exists, read existing users, groups and passwords
if [ -f username.password ]; then
    echo "Reading existing users, groups, and passwords from output file..."
    while IFS= read -r line || [[ -n "$line" ]]; do
        line=$(echo "$line" | xargs)  # Trim whitespace
        if [[ $line == User:* ]]; then
            user=$(echo "$line" | cut -d':' -f2 | xargs)
            arr_users+=("$user")
        elif [[ $line == Group:* ]]; then
            group=$(echo "$line" | cut -d':' -f2 | xargs)
            arr_groups+=("$group")
        elif [[ $line == Password:* ]]; then
            password=$(echo "$line" | cut -d':' -f2 | xargs)
            arr_pass+=("$password")
        fi
    done < username.password
fi
debug-output

# initialize unknown_password variable
unknown_password=0

# increase unkn_password by 1 for each user that has the password "unknown" in the array so far
for i in "${!arr_pass[@]}"; do
    if [[ "${arr_pass[$i]}" == "unknown" ]]; then
        unknown_password=$((unknown_password + 1))
    fi
done

# remove old output file now that we have read the existing users, groups and passwords
rm username.password

echo "Reading users and groups from CSV file..."
# read the CSV file and populate arrays
while IFS=',' read -r user group || [[ -n "$user" ]]; do
    # check if the user already exists in the array
    if [[ " ${arr_users[@]} " =~ " $user " ]]; then
        # user already exists in the array, skipping
        continue
    else
        arr_users+=("$user")  # Add user to the users array
    fi
    # check if the group already exists in the array
    if [[ " ${arr_groups[@]} " =~ " $group " ]]; then
        # group already exists in the array, skipping
        continue
    else
      arr_groups+=("$group")  # Add group to the groups array
    fi
done < users.csv
debug-output

# setting "unknown" password for users that are new to the array but also already exist in the system
for i in "${!arr_users[@]}"; do
    # check if the user already exists in the system
    if id "${arr_users[$i]}" &>/dev/null; then
        # check if the password in the array is empty or unset
        if [[ -z "${arr_pass[$i]}" ]]; then
            # user exists in the system but has no password in the array, set to "unknown"
            arr_pass[$i]="unknown"
            # increase value of "unknown_password" by 1
            unknown_password=$((unknown_password + 1))
        fi
    fi
done

echo "Generating passwords for new users..."
# generate password for the users
while IFS=',' read -r user || [[ -n "$user" ]]; do
    # check if the user already exists
    if id "$user" &>/dev/null; then
        # user already exists, skipping
        continue
    else
        # Generate a random password
        password=$(openssl rand -base64 12)  # Generate a random password
        arr_pass+=("$password")  # Add the password to the arr_pass array
    fi
done < users.csv
debug-output

echo "Adding users and groups (skipping existing accounts)..."
# Add users and groups
for i in "${!arr_users[@]}"; do
    # check if the user already exists
    if id "${arr_users[$i]}" &>/dev/null; then
        # user already exists, skipping
        continue
    else
        # create the user with the generated password
        useradd -m -p "${arr_pass[$i]}" "${arr_users[$i]}"
    fi
    # check if the group already exists
    if getent group "${arr_groups[$i]}" &>/dev/null; then
        # group already exists, skipping
        continue
    else
        # create the group
        groupadd "${arr_groups[$i]}"
    fi
    # add the user to the group
    usermod -aG "${arr_groups[$i]}" "${arr_users[$i]}"
done
debug-output

echo "Creating output file..."
#echo all entries and their users and groups
for i in "${!arr_users[@]}"; do
    echo "------------------------" >> username.password
    echo "Entry $(($i+1)):" >> username.password
    echo "User: ${arr_users[$i]}" >> username.password
    echo "Group: ${arr_groups[$i]}" >> username.password
    echo "Password: ${arr_pass[$i]}" >> username.password
done
echo "------------------------" >> username.password

# set output file permissions to be owned by the user that ran the script (not the root user)
chown "$SUDO_USER":"$(id -gn $SUDO_USER)" username.password

if [ "$unknown_password" -gt 0 ]; then
    echo "There were $unknown_password users with unknown passwords."
    echo "This is because of users existing on the system without corresponding entries in username.password."
fi

echo "Done"