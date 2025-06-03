from traceback import print_tb
import mysql.connector
import time

def main():
	cleanQos(db = getDb("officepc"), raw_data_table = "qos_raw_data", clean_data_table = "flow")
# end def

def cleanQos(db, raw_data_table, clean_data_table):
	cursor = db.cursor()

	# create new table
	cursor.execute(f"DROP TABLE IF EXISTS {clean_data_table};")
	cursor.execute(f"CREATE TABLE {clean_data_table} LIKE {raw_data_table};")

	# get parameter details
	cursor.execute(f"SELECT DISTINCT pocket FROM {raw_data_table} WHERE pocket IS NOT NULL;")
	results = cursor.fetchall()
	pocket = [row[0] for row in results]	# [2, 3, 4, 5, 6, 7, 8, 9]
	print("Pocket       : ", pocket)

	cursor.execute(f"SELECT DISTINCT meter_id FROM {raw_data_table} WHERE meter_id IS NOT NULL;")
	results = cursor.fetchall()
	meter = [row[0] for row in results]	# [1, 2, 3, 4]
	print("Meter id     : ", meter)

	cursor.execute(f"SELECT MIN(trial), MAX(trial) FROM {raw_data_table};")
	results = cursor.fetchall()
	MIN_TRIAL, MAX_TRIAL = results[0][0], results[0][1]
	print("Min/Max trial: ", MIN_TRIAL, MAX_TRIAL)

	cursor.execute(f"SELECT DISTINCT bw FROM {raw_data_table} WHERE bw IS NOT NULL;")
	results = cursor.fetchall()
	bw = [row[0] for row in results]	# ["reg_mid", "reg_end"]
	print("Bw           : ", bw)

	for bwx in bw:
		print(f"├──── Bw - {bwx} - {bw.index(bwx) + 1}/{len(bw)}")
		for pocketx in pocket:
			print(f"│     ├──── Pocket - {pocketx}/{pocket[-1]}")
			for trialx in range(MIN_TRIAL, MAX_TRIAL + 1):
				# determine which rows/stats are useless and which range to save the data from
				def getStartEndId(meter, results):
					ts_id = 0
					diff_sum = [-1 for x in meter]	# to store the s2_byte_in_diff for each meter
					for row in results:
						diff_sum[row[1] - 1] = row[2]	# for each meter id, get the s2_byte_in_diff
						if all(x != -1 for x in diff_sum):	# if all the values in the array have been updated (none are still -1)
							if not any(x is None for x in diff_sum):	# all values are valid values
								if sum(diff_sum) > 0:	# when values start showing up as non zero numbers
									ts_id = row[0]	# this is the row from where the data is valid
									break
							# end if
							diff_sum = [-1 for x in meter]
					# end for
					return ts_id
				# end def

				# get the result for each trial in ascending
				sql_sel = f"""SELECT id, meter_id, s2_byte_in_diff FROM {raw_data_table}
							WHERE bw = "{bwx}" AND pocket = {pocketx} AND trial = {trialx} ORDER BY id ASC, meter_id;"""
				cursor.execute(sql_sel)
				results = cursor.fetchall()
				ts_id_start = getStartEndId(meter, results)

				# get the result for each trial in descending
				sql_sel = f"""SELECT id, meter_id, s2_byte_in_diff FROM {raw_data_table}
							WHERE bw = "{bwx}" AND pocket = {pocketx} AND trial = {trialx} ORDER BY id DESC, meter_id;"""
				cursor.execute(sql_sel)
				results = cursor.fetchall()
				ts_id_end = getStartEndId(meter, results)

				# prepare to move to another table
				sql_ins = f"""INSERT INTO {clean_data_table} SELECT * FROM {raw_data_table}
							WHERE id >= {ts_id_start} AND id <= {ts_id_end} ORDER BY id ASC, meter_id ASC;"""
				cursor.execute(sql_ins)
				db.commit()
			# end for
		# end for
	# end for
# end def

def cleanFlows(db, raw_data_table, clean_data_table):
	cursor = db.cursor()

	# create new table
	cursor.execute(f"DROP TABLE IF EXISTS {clean_data_table};")
	cursor.execute(f"CREATE TABLE {clean_data_table} LIKE {raw_data_table};")

	# get parameter details
	cursor.execute(f"SELECT DISTINCT poll_interval FROM {raw_data_table} WHERE poll_interval IS NOT NULL;")
	results = cursor.fetchall()
	poll_interval = [row[0] for row in results]	# [1, 2, 3]
	print("Poll interval: ", poll_interval)

	cursor.execute(f"SELECT DISTINCT algo FROM {raw_data_table} WHERE algo IS NOT NULL;")
	results = cursor.fetchall()
	algo = [row[0] for row in results]	# ["reg_mid", "reg_end"]
	print("Algo         : ", algo)

	cursor.execute(f"SELECT DISTINCT pocket FROM {raw_data_table} WHERE pocket IS NOT NULL;")
	results = cursor.fetchall()
	pocket = [row[0] for row in results]	# [2, 3, 4, 5, 6, 7, 8, 9]
	print("Pocket       : ", pocket)

	cursor.execute(f"SELECT DISTINCT meter_id FROM {raw_data_table} WHERE meter_id IS NOT NULL;")
	results = cursor.fetchall()
	meter = [row[0] for row in results]	# [1, 2, 3, 4]
	print("Meter id     : ", meter)

	cursor.execute(f"SELECT MIN(trial), MAX(trial) FROM {raw_data_table};")
	results = cursor.fetchall()
	MIN_TRIAL, MAX_TRIAL = results[0][0], results[0][1]
	print("Min/Max trial: ", MIN_TRIAL, MAX_TRIAL)

	for pollx in poll_interval:
		print(f"Poll interval - {pollx}/{poll_interval[-1]}")
		for algox in algo:
			print(f"├──── Algo - {algox} - {algo.index(algox) + 1}/{len(algo)}")
			for pocketx in pocket:
				print(f"│     ├──── Pocket - {pocketx}/{pocket[-1]}")
				for trialx in range(MIN_TRIAL, MAX_TRIAL + 1):
					# determine which rows/stats are useless and which range to save the data from
					def getStartEndId(meter, results):
						ts_id = 0
						diff_sum = [-1 for x in meter]	# to store the s2_byte_in_diff for each meter
						for row in results:
							diff_sum[row[1] - 1] = row[2]	# for each meter id, get the s2_byte_in_diff
							if all(x != -1 for x in diff_sum):	# if all the values in the array have been updated (none are still -1)
								if not any(x is None for x in diff_sum):	# all values are valid values
									if sum(diff_sum) > 0:	# when values start showing up as non zero numbers
										ts_id = row[0]	# this is the row from where the data is valid
										break
								# end if
								diff_sum = [-1 for x in meter]
						# end for
						return ts_id
					# end def

					# get the result for each trial in ascending
					sql_sel = f"""SELECT id, meter_id, s2_byte_in_diff FROM {raw_data_table}
								WHERE poll_interval = {pollx} AND algo = "{algox}" AND pocket = {pocketx} AND trial = {trialx} ORDER BY id ASC, meter_id;"""
					cursor.execute(sql_sel)
					results = cursor.fetchall()
					ts_id_start = getStartEndId(meter, results)

					# get the result for each trial in descending
					sql_sel = f"""SELECT id, meter_id, s2_byte_in_diff FROM {raw_data_table}
								WHERE poll_interval = {pollx} AND algo = "{algox}" AND pocket = {pocketx} AND trial = {trialx} ORDER BY id DESC, meter_id;"""
					cursor.execute(sql_sel)
					results = cursor.fetchall()
					ts_id_end = getStartEndId(meter, results)

					# prepare to move to another table
					sql_ins = f"""INSERT INTO {clean_data_table} SELECT * FROM {raw_data_table}
								WHERE id >= {ts_id_start} AND id <= {ts_id_end} ORDER BY id ASC, meter_id ASC;"""
					cursor.execute(sql_ins)
					db.commit()
				# end for
			# end for
		# end for
	# end for
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