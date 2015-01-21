#!/usr/bin/env python
#
# Created on 9/27/2012 Pat Cappelaere - Vightel Corporation
#
# Daily processing of all products
#
import sys, os, argparse
try:
	from osgeo import osr, gdal
except:
	print "Error", sys.exc_info()[0]
	sys.exit(-1)
	
force 	= 0
verbose = 0
	
def execute(cmd):
	if( force ):
		cmd += " -f"
	
	if(verbose):
		print cmd
		cmd += " -v"
	
	os.system(cmd)
	
def get_daily_precipitation():
	cmd = "./trmm_process.py "
	execute(cmd)

def get_daily_forecast():
	cmd = "./wrfqpe.py "
	execute(cmd)

def get_landslide_nowcast():
	cmd = "./landslide_nowcast.py --region d02 "
	execute(cmd)

	cmd = "./landslide_nowcast.py --region d03 "
	execute(cmd)

def get_flood_nowcast():
	cmd = "./gfms_processing.py"
	execute(cmd)

def get_modis_floodmap():
	cmd = "./modis_floodmap.py"
	execute(cmd)

def restart_ojo_streamer():
	cmd = "cd /Users/patricecappelaere/Development/ojo/ojo-streamer"
	print cmd
	execute(cmd)
	
	cmd = "heroku restart --app ojo-streamer"
	print cmd
	execute(cmd)

def backup_ojo_streamer():
	cmd = "heroku pgbackups:capture --app ojo-streamer HEROKU_POSTGRESQL_COPPER_URL --expire"
	print cmd
	execute(cmd)

def backup_ojo_wiki():
	cmd = "cd /Users/patricecappelaere/Development/ojo/ojo-wiki"
	print cmd
	execute(cmd)

	cmd = "heroku pgbackups:capture --app ojo-wiki HEROKU_POSTGRESQL_ORANGE_URL --expire"
	print cmd
	execute(cmd)
	
#
# ======================================================================
#
if __name__ == '__main__':
	parser 		= argparse.ArgumentParser(description='Landslide/Flood Processing')
	apg_input 	= parser.add_argument_group('Input')
	
	try:
		me 			= sys.argv[0]
		mypath		= os.path.dirname(me) 
	
		print "Process All Path:",  sys.argv[0], mypath
		os.chdir(mypath)
	except:
		print "Unexpected error:", sys.exc_info()[0]
		sys.exit(-1)
	
	
	apg_input.add_argument("-f", "--force", action='store_true', help="forces new prodcuts to be re-generated")
	apg_input.add_argument("-v", "--verbose", action='store_true', help="Verbose Flag")
	
	options 	= parser.parse_args()
	force		= options.force or force
	verbose		= options.verbose or verbose

	#get_daily_precipitation()
	#get_daily_forecast()
	#get_flood_nowcast()
	get_landslide_nowcast()
	#get_modis_floodmap()
	restart_ojo_streamer()
	backup_ojo_streamer()
	backup_ojo_wiki()
	