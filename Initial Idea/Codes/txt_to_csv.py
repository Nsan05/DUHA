import csv

# --- Configuration ---
# Change these two filenames to match your files
input_filename = "C:\\Users\\nithi\\Desktop\\Uni_Stuff\\Y3\\FYP\\Gtfs\\GTFS_20250823\\stop_times.txt"
output_filename = 'C:\\Users\\nithi\\Desktop\\Uni_Stuff\\Y3\FYP\\Codes\\Outputs\\stop_times.csv'
# ---------------------

try:
    with open(input_filename, mode='r', encoding='utf-8') as infile:
        # Create a reader object
        reader = csv.reader(infile)
        
        with open(output_filename, mode='w', encoding='utf-8', newline='') as outfile:
            # Create a writer object.
            # QUOTE_MINIMAL (the default) only quotes fields 
            # that contain special characters (like the delimiter ,)
            writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
            
            # Read each row from the input file and write it to the output file
            for row in reader:
                writer.writerow(row)
                
    print(f"Successfully converted '{input_filename}' to '{output_filename}'")

except FileNotFoundError:
    print(f"Error: The file '{input_filename}' was not found.")
except Exception as e:
    print(f"An error occurred: {e}")