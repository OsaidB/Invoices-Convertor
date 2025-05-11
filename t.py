# Open the input file and read all lines using utf-16
with open('messages.txt', 'r', encoding='utf-16') as infile:
    lines = infile.readlines()

# Filter lines that contain 'address=AL-Eatimad'
filtered_lines = [line for line in lines if 'address=AL-Eatimad' in line]

# Write the filtered lines to the output file using utf-8
with open('output.txt', 'w', encoding='utf-8') as outfile:
    outfile.writelines(filtered_lines)
