import paramiko
import pathlib
import time
import winsound

def main():
	hosts = {}
	hosts["ubuntu"] = {"ip": "192.168.0.100", "user": "deo", "pwd": "deo"}
	hosts["mininet"] = {"ip": "192.168.0.102", "user": "mininet", "pwd": "mininet"}

	user = "deo_k"
	user = "Krish"
	files = []	#files.append(src, dest, host)
	files.append(["C:/Users/" + user + "/Dropbox/Research/Thesis/Code/qostopo-v3.py", "/home/mininet/mininet/custom/qostopo.py", hosts["mininet"]])
	files.append(["C:/Users/" + user + "/Dropbox/Research/Thesis/Code/allocation_app.py", "/home/deo/ryu/ryu/app/adaptive_fair_qos.py", hosts["ubuntu"]])

	print("\nWatching for changes...")
	while True:
		files_to_send = filesToSend(files)
		if(len(files_to_send) > 0):
			sshFtpSend(hosts["mininet"]["ip"], hosts["mininet"]["user"], hosts["mininet"]["pwd"], [f for f in files_to_send if f[2]["ip"] == hosts["mininet"]["ip"]])
			sshFtpSend(hosts["ubuntu"]["ip"], hosts["ubuntu"]["user"], hosts["ubuntu"]["pwd"],    [f for f in files_to_send if f[2]["ip"] == hosts["ubuntu"]["ip"]])
			time_now = time.localtime()
			time_now = time.strftime("%I:%M %p", time_now)
			print("Sent at " + time_now + " ", end = "")
			print(files_to_send)
			print("\nWatching for changes...")
		time.sleep(1)
	#end while
#end def

def filesToSend(files):
	files_to_send = []
	for i in range(len(files)):
		file = pathlib.Path(files[i][0])
		last_mod = file.stat().st_mtime	#in seconds
		time_now = time.time()	#in seconds
		if(time_now - last_mod < 2):
			files_to_send.append(files[i])
	#end for
	return files_to_send
#end def

def sshFtpSend(server_add, usr, pwd, files):
	#make connection
	transport = paramiko.Transport((server_add, 22))
	transport.connect(username = usr, password = pwd)
	sftp = paramiko.SFTPClient.from_transport(transport)

	#send files
	for i in range(len(files)):
		src = files[i][0]
		dest = files[i][1]
		sftp.put(src, dest)
	#end for
	transport.close()
#end def

if __name__ == "__main__":
	main()
#end if