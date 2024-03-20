import os
release_file_path = r"C:\Users\Methusan\Downloads\SM\Spider-Man.Remastered.zip"

# Assuming you want to iterate from 1 to 12
for i in range(14, 36):
    file_number = f"{i:03d}"  # Format the number with leading zeros
    file_path = f'{release_file_path}.{file_number}'
    
    command = f'gh release upload Spider-Man "{file_path}" --clobber'
    
    # Execute the command
    os.system(command)