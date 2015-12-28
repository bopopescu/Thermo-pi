#!/usr/bin/python
# -*- coding: utf-8 -*-

#==================================================================================================================================
#              thermo.py
#----------------------------------------------------------------------------------------------------------------------------------
# by JahisLove - 2014, june
# version 0.1 2014-06-16
#----------------------------------------------------------------------------------------------------------------------------------
# ce script lit les temperatures donnees par 3 sondes DS18B20 reliees au raspberry pi
# et les stock dans une BDD MariaDB
# 
# tested with python 2.7 on Raspberry pi (wheezy) and MariaDB 5.5.34 on NAS Synology DS411J (DSM 5)
#                                                     
#----------------------------------------------------------------------------------------------------------------------------------
#
# la base de données doit avoir cette structure: 
#CREATE TABLE `PiTemp` (
#  `id` int(11) NOT NULL AUTO_INCREMENT,
#  `date` datetime NOT NULL,
#  `sonde1` decimal(3,1) NOT NULL,
#  `sonde2` decimal(3,1) NOT NULL,
#  `sonde3` decimal(3,1) NOT NULL,
#  PRIMARY KEY (`id`)
#) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=28 ;

#==================================================================================================================================

#----------------------------------------------------------#
#             package importation                          #
#----------------------------------------------------------#
import os
#import glob
import time
import MySQLdb   # MySQLdb must be installed by yourself
import sqlite3

#-----------------------------------------------------------------#
#  constants : use your own values / utilisez vos propres valeurs #
#-----------------------------------------------------------------#
PATH_THERM = "/home/pi/thermo/" #path to this script
DB_SERVER ='192.168.0.111'  # MySQL : IP server (localhost if mySQL is on the same machine)
DB_USER='owl_intuition'     # MySQL : user  
DB_PWD='ttp2570'            # MySQL : password 
DB_BASE='owl_intuition'     # MySQL : database name

#base_dir = '/sys/bus/w1/devices/'
#device_folder = glob.glob(base_dir + '28*')[0]
#device_file = '/sys/bus/w1/devices/w1_bus_master1/28-000005f2424d' + '/w1_slave'

sonde1 = "/sys/bus/w1/devices/w1_bus_master1/28-000005f2424d/w1_slave"
sonde2 = "/sys/bus/w1/devices/w1_bus_master1/28-000005f2764e/w1_slave"
sonde3 = "/sys/bus/w1/devices/w1_bus_master1/28-000005f396a0/w1_slave"
sondes = [sonde1, sonde2, sonde3]
sonde_value = [0, 0, 0]

#----------------------------------------------------------#
#             Variables                                    #
#----------------------------------------------------------#

backup_row = 0
backup_mode = 0

if os.path.isfile(PATH_THERM + 'therm_bck.sqlite3'): # if sqlite exist then resume backup mode
    backup_mode = 1

#----------------------------------------------------------#
#     definition : database query with error handling      #
#----------------------------------------------------------#

def query_db(sql):
    global backup_mode
    global backup_row
    try:
        db = MySQLdb.connect(DB_SERVER, DB_USER, DB_PWD, DB_BASE)
        cursor = db.cursor()
        #---------------------------------------------------------------#
        #     Normal MySQL database INSERT                              #
        #---------------------------------------------------------------#
        if backup_mode == 0:
            cursor.execute(sql)
            db.commit()
            db.close()
        #---------------------------------------------------------------#
        # RESTORE : when MySQL is available again : restore from SQlite #
        #---------------------------------------------------------------#
        else:
            logfile = open(PATH_THERM + "thermo.log", "a")
            log = time.strftime('%Y-%m-%d %H:%M:%S') + " INFO : MySQL is OK now : Restore mode started\n"
            logfile.write(log)
            
            db_bck = sqlite3.connect(PATH_THERM + 'therm_bck.sqlite3')
            db_bck.text_factory = str #tell sqlite to work with str instead of unicode
            cursor_bck = db_bck.cursor()

            cursor_bck.execute("""SELECT 'DEFAULT' as id, date, sonde1, sonde2, sonde3 FROM PiTemp ORDER BY date ASC """)
            result_pitemp = cursor_bck.fetchall ()
           
            for row in result_pitemp:
                cursor.execute("""INSERT INTO PiTemp VALUES {0}""".format(row))
                
            db_bck.close()
            log = time.strftime('%Y-%m-%d %H:%M:%S') + " INFO : " + str(backup_row) + " rows restored to MySQL\n"
            logfile.write(log)
           
            backup_row = 0
            backup_mode = 0
            os.remove(PATH_THERM + 'therm_bck.sqlite3')
            log = time.strftime('%Y-%m-%d %H:%M:%S') + " INFO : restore done, sqlite3 file deleted, returning to normal mode\n"
            logfile.write(log)
            
            cursor.execute(sql)
            db.commit()
            db.close()
            logfile.close

        #---------------------------------------------------------------#
        #     BACKUP : when MySQL is down => local SQlite INSERT        #
        #---------------------------------------------------------------#
    except MySQLdb.Error:
        db_bck = sqlite3.connect(PATH_THERM + 'therm_bck.sqlite3')
        cursor_bck = db_bck.cursor()

        if backup_mode == 0: #create table on first run
            logfile = open(PATH_THERM + "thermo.log", "a")
            log = time.strftime('%Y-%m-%d %H:%M:%S') + " WARN : MySQL is down : Backup mode started\n"
            logfile.write(log)
            
            create_pitemp = """CREATE TABLE IF NOT EXISTS PiTemp (`date` datetime NOT NULL,
              sonde1 decimal(3,1) NOT NULL, sonde2 decimal(3,1) NOT NULL,sonde3 decimal(3,1) NOT NULL
            ) ;"""
            
            cursor_bck.execute(create_pitemp)
            
            log = time.strftime('%Y-%m-%d %H:%M:%S') + " WARN : Sqlite created\n"
            logfile.write(log)
            logfile.close

        backup_mode = 1
        cursor_bck.execute(sql)
        backup_row += 1
        db_bck.commit()
        db_bck.close()

#----------------------------------------------------------#
		
def read_file(sonde):
	try:
		f = open(sonde, 'r')
		lines = f.readlines()
		f.close()
	except:
		time.sleep(60)
		try:
			f = open(sonde, 'r')
			lines = f.readlines()
			f.close()
		except:
			# if sonde not found then write to log and set value to 99
			logfile = open(PATH_THERM + "thermo.log", "a")
			log = time.strftime('%Y-%m-%d %H:%M:%S') + " WARN : Sonde not found\n"
			logfile.write(log)
			logfile.close
			lines = ['YES\n', 't=99000']# write  99 to identify problem
			
	finally:
		return lines

#----------------------------------------------------------#
#             code                                         #
#----------------------------------------------------------#

# initialize Raspberry GPIO and DS18B20
os.system('sudo /sbin/modprobe w1-gpio')
os.system('sudo /sbin/modprobe w1-therm')
time.sleep(2)

datebuff = time.strftime('%Y-%m-%d %H:%M:%S') #formating date for mySQL

for (i, sonde) in enumerate(sondes):
	lines = read_file(sonde)
	while lines[0].strip()[-3:] != 'YES': # read 3 last char from line 0 and retry if not yes
		time.sleep(0.2)
		lines = read_file(sonde)

	temp_raw = lines[1].split("=")[1]     # when YES then read temp (after =) in second line
	sonde_value[i] = round(int(temp_raw) / 1000.0, 1)
#	print i, sonde_value[i] #debug

query_db("""INSERT INTO PiTemp (date, sonde1, sonde2, sonde3) VALUES ('%s','%s','%s','%s')
         """ % (datebuff, sonde_value[0], sonde_value[1], sonde_value[2]))



