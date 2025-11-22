import csv
import os

input_file = 'C:\\Users\\nithi\\Desktop\\Uni_Stuff\\Y3\\FYP\\Codes\\input.txt'     # your input file
output_file = 'output.txt'   # file to save filtered data

with open(input_file, 'r', newline='') as infile, open(output_file, 'w', newline='') as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    # Write header
    header = next(reader)
    writer.writerow(header)

    # Keep only rows with MGr or MRe in trip_id
    for row in reader:
        trip_id = row[0]
        if 'MGr' in trip_id or 'MRe' in trip_id:
            writer.writerow(row)

print(f"Filtered records saved to {output_file}")
# Get absolute path of the output file
output_path = os.path.abspath(output_file)
print(f"Filtered records saved to: {output_path}")