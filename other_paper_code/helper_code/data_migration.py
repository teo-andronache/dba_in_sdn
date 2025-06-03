from tkinter import E
import mysql.connector
from tqdm import tqdm

def main():
	migrateData(src_db = getDb("ubuntu"), dst_db = getDb("msi"))
# end def

def migrateData(src_db, dst_db):
	src_table = "qos"
	dst_table = "flow"

	# get the source and destination databases
	dst_cursor = dst_db.cursor()
	src_cursor = src_db.cursor()

	# number of records in source table
	src_cursor.execute(f"SELECT count(*) FROM {src_table};")
	results = src_cursor.fetchall()
	total_src_records = results[0][0]

	# number of records in dest table
	dst_cursor.execute(f"SELECT count(*) FROM {dst_table};")
	results = dst_cursor.fetchall()
	total_dst_records = results[0][0]

	# from the dest table, get the last id - this is where to continue from
	dst_cursor.execute(f"SELECT id FROM {dst_table} ORDER BY id DESC LIMIT 1;")
	results = dst_cursor.fetchall()
	last_id = results[0][0] if results else 0	# if theres no data, then start id from 0

	try:
		total_deleted = 0
		print("Copying data...")
		batch_size = 1000
		total_iterations = 0
		for i in tqdm(range(total_dst_records, total_src_records, batch_size)):
			# not all data for a particular id might have been copied previously because of the LIMIT clause below.
			# hence, for that id, count how many were deleted
			dst_cursor.execute(f"SELECT COUNT(*) FROM {dst_table} WHERE id = {last_id};")
			results = dst_cursor.fetchall()
			total_deleted += results[0][0]

			# now, first delete any partial data from dest DB for that id to insert from that id again
			dst_cursor.execute(f"DELETE FROM {dst_table} WHERE id = {last_id};")
			dst_db.commit()

			# from the last id in the dest table, select the next x rows and copy
			src_cursor.execute(f"SELECT * FROM {src_table} WHERE id >= {last_id} ORDER BY id, meter_id LIMIT {batch_size};")
			results = src_cursor.fetchall()
			if len(results) == 0:	# if no more data is left
				print("No data left, breaking")
				break
			dst_cursor.executemany("INSERT INTO " + dst_table + " VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", results)
			dst_db.commit()

			# get the last id from the flow table in dest db - this is where to continue from
			dst_cursor.execute(f"SELECT id FROM {dst_table} ORDER BY id DESC LIMIT 1;")
			results = dst_cursor.fetchall()
			last_id = results[0][0]
			total_iterations += 1

			#if total_iterations == 100:
			#	break
		# end for
		print("Total iterations: ", total_iterations)
		print("Total deleted: ", total_deleted)
	except Exception as e:
		print(e)
		print("Error occured, rolling back...")
		dst_db.rollback()
	# end try

	# verify the number of rows in both source and destination DB
	print("Verifying records...")
	src_cursor.execute(f"SELECT count(*) FROM {src_table};")
	results = src_cursor.fetchall()
	src_total = results[0][0]
	print(f"""Total records in src DB: {src_total}""")
	dst_cursor.execute(f"SELECT count(*) FROM {dst_table};")
	results = dst_cursor.fetchall()
	dst_total = results[0][0]
	print(f"""Total records in dst DB: {dst_total}""")
	if src_total != dst_total:
		print("Run the code once again to copy the leftover data")
	else:
		print("All data have been copied")

# end def

def getDb(host):
	if host == "ubuntu":
		try:
			db = mysql.connector.connect(host="192.168.0.100", user="deo", password="KrishDeo1#", database="grafana")
			print("Connected to ubuntu")
		except Exception as ex:
			print(ex)
			print("Could not connect to ubuntu")
			exit(0)
	elif host == "msi":
		try:
			db = mysql.connector.connect(host="localhost", user="root", password="", database="research")
			print("Connected to MSI")
		except Exception as ex:
			print(ex)
			print("Could not connect to MSI")
			exit(0)
	elif host == "officepc":
		try:
			db = mysql.connector.connect(host="192.168.0.4", user="root", password="root", database="research")
			print("Connected to officepc")
		except Exception as ex:
			print(ex)
			print("Could not connect to officepc")
			exit(0)
	return db
# end def

if __name__ == "__main__":
	main()
# end if