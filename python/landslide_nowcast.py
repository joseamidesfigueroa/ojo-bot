#!/usr/bin/env python
#
# Created on 11/21/2013 Pat Cappelaere - Vightel Corporation
#
# Generates 24hr Forecast Landslide Estimate
#

import numpy, sys, os, inspect, urllib
import argparse

from osgeo import osr, gdal
from ftplib import FTP
import datetime
from datetime import date, timedelta
from which import *
from dateutil.parser import parse

# Site configuration
import config

force 		= 0
verbose 	= 0
ymd 		= config.ymd

def execute(cmd):
	if(verbose):
		print cmd
	os.system(cmd)
	
def save_tiff(dx, data, fname, ds):
	fullName 	= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, fname+".tif")
	driver 		= gdal.GetDriverByName("GTiff")
	
	out_ds 		= driver.CreateCopy(fullName, ds, 0)
	band		= out_ds.GetRasterBand(1)
	band.WriteArray(data, 0, 0)
	ct = gdal.ColorTable()
	ct.SetColorEntry( 0, (0, 0, 0, 0) )
	ct.SetColorEntry( 1, (255, 0, 0, 255) )
	band.SetRasterColorTable(ct)
	
	out_ds	= None
	
	if verbose:
		print "Created", fullName
		
# Generate Current
def build_tif(dx, region, dir, date):
	region 		= config.regions[dx]
	bbox		= region['bbox']
	tzoom   	= region['tiles-zoom']
	pixelsize   = region['pixelsize']
	thn_width   = region['thn_width']
	thn_height  = region['thn_height']
	bucketName 	= region['bucket']

	# get the low percentile rainfall limits
	limit_low = os.path.join(config.data_dir,"ant_r", "%s_50r.tif" % (dx))
	if not os.path.exists(limit_low):
		print "**ERR: file not found", limit_low
		sys.exit(-1)

	# get the high percentile rainfall limits
	limit_high = os.path.join(config.data_dir,"ant_r", "%s_90r.tif" % (dx))
	if not os.path.exists(limit_high):
		print "**ERR: file not found", limit_high
		sys.exit(-1)

	# get the 95th percentile antecedent rainfall limits
	#limit_95 = os.path.join(config.data_dir,"ant_r", "%s_95ar.tif" % (dx))
	#if not os.path.exists(limit_95):
	#	print "**ERR: file not found", limit_95
	#	sys.exit(-1)

	# Find the antecedent rainfall boolean 95th percentile accumulation file for the area
	ant_rainfall_bool 	= os.path.join(config.data_dir,"ant_r", dx, ymd, "ant_r_%s_bool.tif" % (ymd))
	if force or not os.path.exists(ant_rainfall_bool):
		cmd = "antecedent_rainfall.py --region "+dx+ " --date "+date
		if verbose:
			cmd += " -v"
		if force:
			cmd += " -f"
		execute(cmd)
	
	# Find the daily rainfall accumulation file for the area from yesterday
	daily_rainfall 	= os.path.join(config.data_dir,"trmm", dx, yymd, "trmm_24_%s_%s_1km.tif" % (dx,yymd))
	if not os.path.exists(daily_rainfall):
		print "**ERR: file not found", daily_rainfall
		sys.exit(-1)
		
	# Find susceptibility map
	susmap 	= os.path.join(config.data_dir, "susmap.2", "susmap_%s_bool.tif" %(dx))
	if not os.path.exists(susmap):
		print "**ERR: file not found", susmap
		sys.exit(-1)

	forecast_landslide_bin 				= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.tif" %(dx,ymd))
	forecast_landslide_bin_rgb 			= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s_rgb.tif" %(dx,ymd))

	forecast_landslide_100m_bin 		= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s_100m.tif" %(dx,ymd))
	forecast_landslide_100m_bin_rgb 	= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s_100m_rgb.tif" %(dx,ymd))
		
	color_file							= "./cluts/landslide_colors.txt"
	
	shp_file 							= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.shp" % (dx,ymd))
	geojson_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.geojson" % (dx,ymd))
	
	topojson_file						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.topojson" % (dx,ymd))
	topojson_gz_file					= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.topojson.gz" % (dx,ymd))
	thumbnail_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast_%s_%s.thn.png" % (dx,ymd))
	static_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, "%s_static.tiff" % (dx))

	if force or not os.path.exists(forecast_landslide_bin):
		if verbose:
			"Processing forecast landslide model for %s..." % config.ym
			
		if verbose:
			print "Loading ", susmap

		# STEP 1 Susceptibility Map as Boolean
		smap_ds			= gdal.Open( susmap )
		smap_ncols 		= smap_ds.RasterXSize
		smap_nrows 		= smap_ds.RasterYSize
		smap_band 		= smap_ds.GetRasterBand(1)
		smap_data 		= smap_band.ReadAsArray(0, 0, smap_ncols, smap_nrows )
		projection   	= smap_ds.GetProjection()
		geotransform 	= smap_ds.GetGeoTransform()

		xorg			= geotransform[0]
		yorg  			= geotransform[3]
		pres			= geotransform[1]
		xmax			= xorg + geotransform[1]* smap_ds.RasterXSize
		ymax			= yorg - geotransform[1]* smap_ds.RasterYSize
			
		if verbose:
			print "Loading ", daily_rainfall

		rainfall_ds		= gdal.Open( daily_rainfall )
		rainfall_ncols 	= rainfall_ds.RasterXSize
		rainfall_nrows 	= rainfall_ds.RasterYSize
		rainfall_band 	= rainfall_ds.GetRasterBand(1)
		rainfall_data 	= rainfall_band.ReadAsArray(0, 0, rainfall_ncols, rainfall_nrows )
	
		assert( smap_ncols == rainfall_ncols)
		assert( smap_nrows == rainfall_nrows)

		if verbose:
			print "Loading ", ant_rainfall_bool

		ant_rainfall_ds			= gdal.Open( ant_rainfall_bool )
		ant_rainfall_ncols 		= ant_rainfall_ds.RasterXSize
		ant_rainfall_nrows 		= ant_rainfall_ds.RasterYSize
		ant_rainfall_band 		= ant_rainfall_ds.GetRasterBand(1)
		ant_rainfall_data_bool 	= ant_rainfall_band.ReadAsArray(0, 0, ant_rainfall_ncols, ant_rainfall_nrows )

		assert( smap_ncols == ant_rainfall_ncols)
		assert( smap_nrows == ant_rainfall_nrows)
	
		if verbose:
			print "cols %d rows %d" %(ant_rainfall_ncols, ant_rainfall_nrows)

		if verbose:
			print "Loading ", limit_low
			
		limit_low_ds		= gdal.Open( limit_low )
		limit_low_ncols 	= limit_low_ds.RasterXSize
		limit_low_nrows 	= limit_low_ds.RasterYSize
		limit_low_band 		= limit_low_ds.GetRasterBand(1)
		limit_low_data 		= limit_low_band.ReadAsArray(0, 0, limit_low_ncols, limit_low_nrows )

		assert( smap_ncols == limit_low_ncols)
		assert( smap_nrows == limit_low_nrows)
		
		if verbose:
			print "Loading ", limit_high
			
		limit_high_ds		= gdal.Open( limit_high )
		limit_high_ncols 	= limit_high_ds.RasterXSize
		limit_high_nrows 	= limit_high_ds.RasterYSize
		limit_high_band 	= limit_high_ds.GetRasterBand(1)
		limit_high_data 	= limit_high_band.ReadAsArray(0, 0, limit_high_ncols, limit_high_nrows )

		assert( smap_ncols == limit_high_ncols)
		assert( smap_nrows == limit_high_nrows)

		# Step 2
		# low percentile current rainfall raster
		rr_low = numpy.zeros(shape=(rainfall_nrows,rainfall_ncols))
		rr_low[rainfall_data > limit_low_data] = 1
		
		if verbose:
			save_tiff(dx, rr_low,"rr_low", smap_ds)
			
		# Step 3
		# high percentile current rainfall raster
		rr_high = numpy.zeros(shape=(rainfall_nrows,rainfall_ncols))
		rr_high[rainfall_data > limit_high_data] = 1
		if verbose:
			save_tiff(dx, rr_high, "rr_high", smap_ds)
			
		# inverted antecedent boolean raster
		iabr = numpy.zeros(shape=(ant_rainfall_nrows,ant_rainfall_ncols))
		iabr[ant_rainfall_data_bool == 0] = 1
		if verbose:
			save_tiff(dx, iabr, "iabr", smap_ds)
			
		# Step 4
		# antecedent boolean raster is ant_rainfall_data
		step_8_1 = numpy.logical_and(ant_rainfall_data_bool, rr_low)
		if verbose:
			save_tiff(dx, step_8_1, "step_8_1", smap_ds)
		
		step_8_2 = numpy.logical_and(iabr, rr_high)
		if verbose:
			save_tiff(dx, step_8_2, "step_8_2", smap_ds)
		
		step_8_3 = numpy.logical_or(step_8_1, step_8_2)
		if verbose:
			save_tiff(dx, step_8_3, "step_8_3", smap_ds)
		
		step_8_4 = numpy.logical_and(smap_data, step_8_3)
		if verbose:
			save_tiff(dx, step_8_4, "step_8_4", smap_ds)

		# Write the file
		driver 			= gdal.GetDriverByName("GTiff")
		cur_ds 			= driver.Create(forecast_landslide_bin, smap_ncols, smap_nrows, 1, gdal.GDT_Byte)
		outband 		= cur_ds.GetRasterBand(1)
		
		outband.WriteArray(step_8_4, 0, 0)

		cur_ds.SetGeoTransform( geotransform )
		cur_ds.SetGeoTransform( geotransform )

		smap_ds 		= None
		rainfall_ds 	= None
		ant_rainfall_ds = None
		cur_ds			= None
		limit_low_ds	= None
		limit_high_ds	= None

	# Now let's colorize it
	if 1: #force or not os.path.exists(forecast_landslide_bin_rgb):
		cmd = "gdaldem color-relief -alpha " +  forecast_landslide_bin + " " + color_file + " " + forecast_landslide_bin_rgb
		if verbose:
			print cmd
		err = os.system(cmd)
		if err != 0:
			print('ERROR: slope file could not be generated:', err)
			sys.exit(-1)
	

	infile 	= forecast_landslide_bin_rgb
	file 	= forecast_landslide_bin_rgb + ".pgm"

	if force or not os.path.exists(file):
		# subset it, convert red band (band 1) and output to .pgm using PNM driver
		cmd = "gdal_translate  -q -scale 0 1 0 65535 " + infile + " -b 1 -of PNM -ot Byte "+file
		execute( cmd )
		execute("rm -f "+file+".aux.xml")

	# -i  		invert before processing
	# -t 2  	suppress speckles of up to this many pixels. 
	# -a 1.5  	set the corner threshold parameter
	# -z black  specify how to resolve ambiguities in path decomposition. Must be one of black, white, right, left, minority, majority, or random. Default is minority
	# -x 		scaling factor
	# -L		left margin
	# -B		bottom margin

	if force or not os.path.exists(file+".geojson"):
		cmd = str.format("potrace -z black -a 1.5 -t 2 -i -b geojson -o {0} {1} -x {2} -L {3} -B {4} ", file+".geojson", file, pres, xorg, ymax ); 
		execute(cmd)

	if force or not os.path.exists(file+".topojson.gz"):
		cmd = str.format("topojson -o {0} --simplify-proportion 0.5 -p nowcast=1 -- landslide_nowcast={1}", file+".topojson", file+".geojson"); 
		execute(cmd)
	
		cmd = "gzip %s" % (file+".topojson")
		execute(cmd)

		cmd = "mv " + file+".topojson.gz" + " " + topojson_gz_file
		execute(cmd)
		
	#create the thumbnail
	tmp_file = thumbnail_file + ".tmp.tif"
	if force or not os.path.exists(thumbnail_file):
		cmd="gdalwarp -overwrite -q -multi -ts %d %d -r cubicspline -co COMPRESS=LZW %s %s" % (thn_width, thn_height, forecast_landslide_bin_rgb, tmp_file )
		execute(cmd)
		cmd = "composite %s %s %s" % ( tmp_file, static_file, thumbnail_file)
		execute(cmd)
		execute("rm "+tmp_file)
	
	if not verbose:
		files = [ "*.tif", file,file+".geojson", file+".geojson",forecast_landslide_bin, forecast_landslide_bin_rgb   ]
		execute("rm -f "+" ".join(files))
		
	cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + topojson_gz_file
	if verbose:
		cmd += " --verbose"
	if force:
		cmd += " --force"
	execute(cmd)

	cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + thumbnail_file
	if verbose:
		cmd += " --verbose"
	if force:
		cmd += " --force"
		
	execute(cmd)
	
def generate_map( dx, date ):
	# make sure it exists
	region		= config.regions[dx]
	
	if verbose:
		print "Processing Forecast Landslide Map for Region:", dx, region['name']	
	
	# Destination Directory
	dir			= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd)
	if not os.path.exists(dir):
		os.makedirs(dir)

	build_tif(dx, region, dir, date )

# =======================================================================
# Main
#
if __name__ == '__main__':
	
	parser 		= argparse.ArgumentParser(description='Generate Forecast Landslide Estimates')
	apg_input 	= parser.add_argument_group('Input')
		
	apg_input.add_argument("-f", "--force", 	action='store_true', help="Forces new products to be generated")
	apg_input.add_argument("-v", "--verbose", 	action='store_true', help="Verbose Flag")
	apg_input.add_argument("-r", "--region", 	required=True, help="Region: d02|d03")
	apg_input.add_argument("-d", "--date", 		help="date: 2014-11-20 or today if not defined")
	
	todaystr	= date.today().strftime("%Y-%m-%d")
	
	options 	= parser.parse_args()
	force		= options.force
	verbose		= options.verbose
	region		= options.region
	dt			= options.date or todaystr
	
	assert(config.regions[region])
	
	today		= parse(dt)
	year		= today.year
	month		= today.month
	day			= today.day
	ymd			= "%d%02d%02d" % (year, month, day)

	yesterday	= today - timedelta(days=1)
	yyear		= yesterday.year
	ymonth		= yesterday.month
	yday		= yesterday.day
	yymd		= "%d%02d%02d" % (yyear, ymonth, yday)
	
	if verbose:
		print "generating forecast for", today.strftime("%Y-%m-%d")
		
	generate_map(region, dt)
	
	print "Done."