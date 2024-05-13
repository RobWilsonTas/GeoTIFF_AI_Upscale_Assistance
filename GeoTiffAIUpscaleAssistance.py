import numpy
import subprocess
import os
import glob
import time
from qgis.core import QgsRasterLayer
from qgis.PyQt.QtWidgets import QMessageBox
from datetime import datetime
startTime = time.time()

"""
##########################################################
User options
"""

#Variable assignment
inImage                 = 'D:/Temp/YourImage.tif'        #E.g 'C:/ImageEnhance/AerialImagery.tif'
approxPixelsPerTile     = 2750                          #E.g 2750, this is based on the maximum input resolution of the AI upscaler

#Options for compressing the images, ZSTD has the best speed but LZW is the most compatible
compressOptions         = 'COMPRESS=ZSTD|NUM_THREADS=ALL_CPUS|PREDICTOR=1|ZSTD_LEVEL=1|BIGTIFF=IF_SAFER|TILED=YES'

"""
##########################################################
Variable assignment for processing
"""

#Get the location of the initial image for storage of processing files
rootProcessDirectory = str(Path(inImage).parent.absolute()).replace('\\','/') + '/'

#Set up the layer name for the raster calculations
inImageName = inImage.split("/")
inImageName = inImageName[-1]
inImageName = inImageName[:len(inImageName)-4]
inImageName = inImageName[:8]
outImageName = inImageName

#Making a folder for processing each time, to avoid issues with locks
processDirectoryInstance = rootProcessDirectory + inImageName + 'Process' + '/'

#Creating all the subfolder variables
processDirectory                = processDirectoryInstance + '1Main/'
processBoundsDirectory          = processDirectoryInstance + '2TileBounds/'
processBoundsSmallerDirectory   = processDirectoryInstance + '3TileBoundsSmaller/'
processTileDirectory            = processDirectoryInstance + '4Tiles/'
aiOutputReffedDirectory         = processDirectoryInstance + '6AIOutputReffed/'
aiOutputDirectory               = processDirectoryInstance + '5AIOutput/'
aiOutputRefClipDirectoryRoot    = processDirectoryInstance + '7AIOutputRefClip/'
aiOutputRefClipDirectory1       = processDirectoryInstance + '7AIOutputRefClip/1/'
aiOutputRefClipDirectory2       = processDirectoryInstance + '7AIOutputRefClip/2/'
aiOutputRefClipDirectory3       = processDirectoryInstance + '7AIOutputRefClip/3/'
aiOutputRefClipDirectory4       = processDirectoryInstance + '7AIOutputRefClip/4/'
stagingImageDir                 = processDirectoryInstance + '8StagingImages/'
finalImageDir                   = processDirectoryInstance + '9Final/'

#Creating all the subfolders
try:
    os.mkdir(processDirectoryInstance)
    os.mkdir(processDirectory)
    os.mkdir(processBoundsDirectory)
    os.mkdir(processBoundsSmallerDirectory)
    os.mkdir(processTileDirectory)
    os.mkdir(aiOutputReffedDirectory)
    os.mkdir(aiOutputDirectory)
    os.mkdir(aiOutputRefClipDirectoryRoot)
    os.mkdir(aiOutputRefClipDirectory1)
    os.mkdir(aiOutputRefClipDirectory2)
    os.mkdir(aiOutputRefClipDirectory3)
    os.mkdir(aiOutputRefClipDirectory4)
    os.mkdir(stagingImageDir)
    os.mkdir(finalImageDir)
except BaseException as e:
    print ('Couldnt make the directory because... ')
    print(e)


"""
####################################################################################
"""

#Get the pixel size and coordinate system of the raster
ras = QgsRasterLayer(inImage)
pixelSizeX = ras.rasterUnitsPerPixelX()
pixelSizeY = ras.rasterUnitsPerPixelY()
pixelSizeAve = (pixelSizeX + pixelSizeY) / 2
coordinateSystem = ras.crs().authid()


#Ask the user if they need to split up the raster, this isn't required if they have already run this section
promptReply = QMessageBox.question(iface.mainWindow(), 'Does the raster need splitting up?', "Do you need to perform tiling?\n\nIf you don't, make sure that all the tifs are in " + processTileDirectory + " before you click no\n\nIf you do, tiling will be performed on " + inImage + " when you click yes", QMessageBox.Yes, QMessageBox.No)
if promptReply == QMessageBox.Yes:

    #Clear out the folders
    files = glob.glob(processDirectory + '*')
    for f in files:
        try:
            os.remove(f) 
        except BaseException as e:
            print(e)
            
    boundsFiles = glob.glob(processBoundsDirectory + '*')
    for f in boundsFiles:
        try:
            os.remove(f) 
        except BaseException as e:
            print(e)
            
    boundsSmallerFiles = glob.glob(processBoundsSmallerDirectory + '*')
    for f in boundsSmallerFiles:
        try:
            os.remove(f) 
        except BaseException as e:
            print(e)
            
    tileFiles = glob.glob(processTileDirectory + '*')
    for f in tileFiles:
        try:
            os.remove(f) 
        except BaseException as e:
            print(e)
            theseFilesHaveToGo

    """
    ###############################################################################################
    """

    #Get the extent of the image where there is alpha
    processing.run("gdal:translate", {'INPUT':inImage,'TARGET_CRS':None,'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-b 4 -scale_1 128 255 -1000 1255','DATA_TYPE':0,'OUTPUT':processDirectory + inImageName + 'AlphaClean.tif'})
    processing.run("gdal:polygonize", {'INPUT':processDirectory + inImageName + 'AlphaClean.tif','BAND':1,'FIELD':'DN','EIGHT_CONNECTEDNESS':False,'EXTRA':'','OUTPUT':processDirectory + inImageName + 'Extent.gpkg'})
    processing.run("native:fixgeometries", {'INPUT':processDirectory + inImageName + 'Extent.gpkg','OUTPUT':processDirectory + inImageName + 'ExtentFix.gpkg'})
    processing.run("native:extractbyexpression", {'INPUT':processDirectory + inImageName + 'ExtentFix.gpkg','EXPRESSION':' \"DN\" > 245','OUTPUT':processDirectory + inImageName + 'ExtentFilt.gpkg'})

    #Determine the extent and coordinate system of the extent
    fullExtentForCutline = processDirectory + inImageName + 'ExtentFilt.gpkg'
    extentVector = QgsVectorLayer(processDirectory + inImageName + 'ExtentFilt.gpkg')
    extentRectangle = extentVector.extent()
    extentCrs = extentVector.sourceCrs()
    
    #Then close the layer object so that QGIS doesn't unnecessarily hold on to it
    QgsProject.instance().addMapLayer(extentVector, False)
    QgsProject.instance().removeMapLayer(extentVector.id())

    #Create a grid for dividing the image up into tiles
    processing.run("native:creategrid", {'TYPE':2,'EXTENT':extentRectangle,'HSPACING':pixelSizeX * approxPixelsPerTile,'VSPACING':pixelSizeY * approxPixelsPerTile,'HOVERLAY':0,'VOVERLAY':0,'CRS':extentCrs,'OUTPUT':processDirectory + inImageName + 'ExtentFiltGrid.gpkg'})

    #Buffer it out so that we have space for clipping 
    processing.run("native:buffer", {'INPUT':processDirectory + inImageName + 'ExtentFiltGrid.gpkg','DISTANCE':pixelSizeAve * 100,'SEGMENTS':5,'END_CAP_STYLE':0,'JOIN_STYLE':1,'MITER_LIMIT':2,'DISSOLVE':False,'OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBuffer.gpkg'})

    #Only grab the part of the grid that will actually be relevant
    processing.run("native:extractbylocation", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBuffer.gpkg','PREDICATE':[0,4,5],'INTERSECT':processDirectory + inImageName + 'ExtentFilt.gpkg','OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBufferGrabbed.gpkg'})

    #Clip this so we're not overrunning and getting AI to upscale an area of black
    processing.run("native:clip", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBufferGrabbed.gpkg','OVERLAY':processDirectory + inImageName + 'ExtentFilt.gpkg','OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBufferGrabbedClip.gpkg'})

    #Split it out so there is a different extent to work from for each instance of the raster clipping
    processing.run("native:splitvectorlayer", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBufferGrabbedClip.gpkg','FIELD':'id','FILE_TYPE':0,'OUTPUT':processBoundsDirectory})


    """
    ##################################
    """
    
    
    #Buffer it out so that we have space for clipping 
    processing.run("native:buffer", {'INPUT':processDirectory + inImageName + 'ExtentFiltGrid.gpkg','DISTANCE':pixelSizeAve * 75,'SEGMENTS':5,'END_CAP_STYLE':0,'JOIN_STYLE':1,'MITER_LIMIT':2,'DISSOLVE':False,'OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmaller.gpkg'})

    #Only grab the part of the grid that will actually be relevant
    processing.run("native:extractbylocation", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmaller.gpkg','PREDICATE':[0,4,5],'INTERSECT':processDirectory + inImageName + 'ExtentFilt.gpkg','OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmallerGrabbed.gpkg'})

    #Clip this so we're not overrunning and getting AI to upscale an area of black
    processing.run("native:clip", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmallerGrabbed.gpkg','OVERLAY':processDirectory + inImageName + 'ExtentFilt.gpkg','OUTPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmallerGrabbedClip.gpkg'})

    #Split it out so there is a different extent to work from for each instance of the raster clipping
    processing.run("native:splitvectorlayer", {'INPUT':processDirectory + inImageName + 'ExtentFiltGridBufferSmallerGrabbedClip.gpkg','FIELD':'id','FILE_TYPE':0,'OUTPUT':processBoundsSmallerDirectory})


    """
    #################################################################################################
    """
    #Take away the alpha band, this is not needed for the AI algorithm
    processing.run("gdal:translate", {'INPUT':inImage,'TARGET_CRS':None,'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-b 1 -b 2 -b 3','DATA_TYPE':0,'OUTPUT':processDirectory + 'RemoveAlphaBand.tif'})

    #Get all of the sections of the grid
    boundsFiles = glob.glob(processBoundsDirectory + '/*')

    #Split the list of grid sections into quarters, ready for multiprocessing
    boundsNo1 = boundsFiles[0::4]
    boundsNo2 = boundsFiles[1::4]
    boundsNo3 = boundsFiles[2::4]
    boundsNo4 = boundsFiles[3::4]


    #Define the multiprocessing tasks
    #Here the tile extents will be used to clip the raster into a bunch of tiles, which are then to be given to the AI
    def one(task):
        for indivBound in boundsNo1:
            boundName = indivBound.split('\\')[-1]
            boundName = boundName.split('.')[0]
            processing.run("gdal:cliprasterbymasklayer", {'INPUT':processDirectory + 'RemoveAlphaBand.tif','MASK':indivBound,'SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':processTileDirectory  + boundName + 'Tile.png'})
        print("Done pt.1")
    def two(task):
        for indivBound in boundsNo2:
            boundName = indivBound.split('\\')[-1]
            boundName = boundName.split('.')[0]
            processing.run("gdal:cliprasterbymasklayer", {'INPUT':processDirectory + 'RemoveAlphaBand.tif','MASK':indivBound,'SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':processTileDirectory  + boundName + 'Tile.png'})
        print("Done pt.2")
    def three(task):
        for indivBound in boundsNo3:
            boundName = indivBound.split('\\')[-1]
            boundName = boundName.split('.')[0]
            processing.run("gdal:cliprasterbymasklayer", {'INPUT':processDirectory + 'RemoveAlphaBand.tif','MASK':indivBound,'SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':processTileDirectory  + boundName + 'Tile.png'})
        print("Done pt.3")
    def four(task):
        for indivBound in boundsNo4:
            boundName = indivBound.split('\\')[-1]
            boundName = boundName.split('.')[0]
            processing.run("gdal:cliprasterbymasklayer", {'INPUT':processDirectory + 'RemoveAlphaBand.tif','MASK':indivBound,'SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':processTileDirectory  + boundName + 'Tile.png'})
        print("Done pt.4")

    #Assign the functions to a Qgs task
    task1 = QgsTask.fromFunction('TilerProcess', one)
    task2 = QgsTask.fromFunction('ItWorks2', two)
    task3 = QgsTask.fromFunction('ItWorks3', three)
    task4 = QgsTask.fromFunction('ItWorks4', four)

    #Combine and run the tasks
    task1.addSubTask(task2)
    task1.addSubTask(task3)
    task1.addSubTask(task4)
    QgsApplication.taskManager().addTask(task1)

    print("The tasks are now running in the background, you can check task manager for CPU usage")

    """
    #################################################################################################
    """

    #Wait for the tiling to finish...
    try:
        task1.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)


"""
#######################################################################
Georef the results from the AI
"""

#If the images have been upscaled through the AI program, we can run the next section
promptReply = QMessageBox.question(iface.mainWindow(), 'Are we ready to ref the AI tiles?', 'Have the tiles in ' + processTileDirectory + ' been put through the AI program?\n\nAre we ready for the AI output to be reffed?', QMessageBox.Yes, QMessageBox.No)
if promptReply == QMessageBox.Yes:

    reffedFiles = glob.glob(aiOutputReffedDirectory + '*')
    for f in reffedFiles:
        try:
            os.remove(f) 
        except BaseException as e:
            print(e)    
    

    #This looks to see what .pngs are in the directory for the AI outputs to go, and runs through them
    tileFiles = glob.glob(aiOutputDirectory + '/*.png')
    
    
    #Split the list of grid sections into quarters, ready for multiprocessing
    tilesNo1 = tileFiles[0::4]
    tilesNo2 = tileFiles[1::4]
    tilesNo3 = tileFiles[2::4]
    tilesNo4 = tileFiles[3::4]


    #Define the multiprocessing tasks
    #Here the tile extents will be used to clip the raster into a bunch of tiles, which are then to be given to the AI
    def one(task):
        for indivTile1 in tilesNo1:
            tileName1 = indivTile1.split('\\')[-1]
            tileName1 = tileName1.split('.')[0]
            #Grabbing the extent of the original tile, given that the AI program won't preserve georeferencing
            origRas1 = QgsRasterLayer(processTileDirectory + tileName1 + '.png')
            origRasBounds1 = origRas1.extent()
            xmin1 = origRasBounds1.xMinimum()
            xmax1 = origRasBounds1.xMaximum()
            ymin1 = origRasBounds1.yMinimum()
            ymax1 = origRasBounds1.yMaximum()
            coords1 = "%f %f %f %f" %(xmin1, ymax1, xmax1, ymin1)
            #Finally the AI upscaled image will be georeferenced based on what it was before being AI upscaled
            processing.run("gdal:translate", {'INPUT':aiOutputDirectory + tileName1 + '.png','TARGET_CRS':QgsCoordinateReferenceSystem(coordinateSystem),'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-a_ullr ' + coords1,'DATA_TYPE':0,'OUTPUT':aiOutputReffedDirectory + tileName1 + 'Reffed.tif'})
        print("Done pt.1")
        
    def two(task):
        for indivTile2 in tilesNo2:
            tileName2 = indivTile2.split('\\')[-1]
            tileName2 = tileName2.split('.')[0]
            #Grabbing the extent of the original tile, given that the AI program won't preserve georeferencing
            origRas2 = QgsRasterLayer(processTileDirectory + tileName2 + '.png')
            origRasBounds2 = origRas2.extent()
            xmin2 = origRasBounds2.xMinimum()
            xmax2 = origRasBounds2.xMaximum()
            ymin2 = origRasBounds2.yMinimum()
            ymax2 = origRasBounds2.yMaximum()
            coords2 = "%f %f %f %f" %(xmin2, ymax2, xmax2, ymin2)
            #Finally the AI upscaled image will be georeferenced based on what it was before being AI upscaled
            processing.run("gdal:translate", {'INPUT':aiOutputDirectory + tileName2 + '.png','TARGET_CRS':QgsCoordinateReferenceSystem(coordinateSystem),'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-a_ullr ' + coords2,'DATA_TYPE':0,'OUTPUT':aiOutputReffedDirectory + tileName2 + 'Reffed.tif'})
        print("Done pt.2")
        
    def three(task):
        for indivTile3 in tilesNo3:
            tileName3 = indivTile3.split('\\')[-1]
            tileName3 = tileName3.split('.')[0]
            #Grabbing the extent of the original tile, given that the AI program won't preserve georeferencing
            origRas3 = QgsRasterLayer(processTileDirectory + tileName3 + '.png')
            origRasBounds3 = origRas3.extent()
            xmin3 = origRasBounds3.xMinimum()
            xmax3 = origRasBounds3.xMaximum()
            ymin3 = origRasBounds3.yMinimum()
            ymax3 = origRasBounds3.yMaximum()
            coords3 = "%f %f %f %f" %(xmin3, ymax3, xmax3, ymin3)
            #Finally the AI upscaled image will be georeferenced based on what it was before being AI upscaled
            processing.run("gdal:translate", {'INPUT':aiOutputDirectory + tileName3 + '.png','TARGET_CRS':QgsCoordinateReferenceSystem(coordinateSystem),'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-a_ullr ' + coords3,'DATA_TYPE':0,'OUTPUT':aiOutputReffedDirectory + tileName3 + 'Reffed.tif'})
        print("Done pt.3")
    
    def four(task):
        for indivTile4 in tilesNo4:
            tileName4 = indivTile4.split('\\')[-1]
            tileName4 = tileName4.split('.')[0]
            #Grabbing the extent of the original tile, given that the AI program won't preserve georeferencing
            origRas4 = QgsRasterLayer(processTileDirectory + tileName4 + '.png')
            origRasBounds4 = origRas4.extent()
            xmin4 = origRasBounds4.xMinimum()
            xmax4 = origRasBounds4.xMaximum()
            ymin4 = origRasBounds4.yMinimum()
            ymax4 = origRasBounds4.yMaximum()
            coords4 = "%f %f %f %f" %(xmin4, ymax4, xmax4, ymin4)
            #Finally the AI upscaled image will be georeferenced based on what it was before being AI upscaled
            processing.run("gdal:translate", {'INPUT':aiOutputDirectory + tileName4 + '.png','TARGET_CRS':QgsCoordinateReferenceSystem(coordinateSystem),'NODATA':None,'COPY_SUBDATASETS':False,'OPTIONS':compressOptions,'EXTRA':'-a_ullr ' + coords4,'DATA_TYPE':0,'OUTPUT':aiOutputReffedDirectory + tileName4 + 'Reffed.tif'})
        print("Done pt.4")

    #Assign the functions to a Qgs task
    task1 = QgsTask.fromFunction('ReferencerProcess', one)
    task2 = QgsTask.fromFunction('ItWorks2', two)
    task3 = QgsTask.fromFunction('ItWorks3', three)
    task4 = QgsTask.fromFunction('ItWorks4', four)

    #Combine and run the tasks
    QgsApplication.taskManager().addTask(task1)
    QgsApplication.taskManager().addTask(task2)
    QgsApplication.taskManager().addTask(task3)
    QgsApplication.taskManager().addTask(task4)

    print("The tasks are now running in the background, you can check task manager for CPU usage")

    """
    #################################################################################################
    """

    #Wait for the georeferencing to finish...
    try:
        task1.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
    try:
        task2.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
    try:
        task3.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
    try:
        task4.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
    
    print("Ok the referencing section is done, now let's go for the clipping section")

    
    """
    #######################################################################
    Clipping the raster so that the overlap looks good
    """
    
    reffedFiles = glob.glob(aiOutputReffedDirectory + '/*.tif')
    
    #Code to split the list in quarters ready for multiprocessing
    k, m = divmod(len(reffedFiles), 4)
    partitionedList = list(reffedFiles[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(4))
    
    reffedTilesNo1 = partitionedList[0]
    reffedTilesNo2 = partitionedList[1]
    reffedTilesNo3 = partitionedList[2]
    reffedTilesNo4 = partitionedList[3]
    
    
    def one(task):
        try:
            for indivTile1 in reffedTilesNo1:
                tileName1 = indivTile1.split('\\')[-1]
                tileName1 = tileName1.split('.')[0]
                tileName1 = tileName1[:-10]
                processing.run("gdal:cliprasterbymasklayer", {'INPUT':aiOutputReffedDirectory + tileName1 + 'TileReffed.tif','MASK':processBoundsSmallerDirectory + tileName1 + '.gpkg','SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':compressOptions,'DATA_TYPE':0,'EXTRA':'','OUTPUT':aiOutputRefClipDirectory1  + tileName1 + 'RefClipTile.tif'})
            print("Done pt.1")
        except BaseException as e:
            print (e)
    
    def two(task):
        try:
            for indivTile2 in reffedTilesNo2:
                tileName2 = indivTile2.split('\\')[-1]
                tileName2 = tileName2.split('.')[0]
                tileName2 = tileName2[:-10]
                processing.run("gdal:cliprasterbymasklayer", {'INPUT':aiOutputReffedDirectory + tileName2 + 'TileReffed.tif','MASK':processBoundsSmallerDirectory + tileName2 + '.gpkg','SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':compressOptions,'DATA_TYPE':0,'EXTRA':'','OUTPUT':aiOutputRefClipDirectory2  + tileName2 + 'RefClipTile.tif'})
            print("Done pt.2")
        except BaseException as e:
            print (e)
            
    def three(task):
        try:
            for indivTile3 in reffedTilesNo3:
                tileName3 = indivTile3.split('\\')[-1]
                tileName3 = tileName3.split('.')[0]
                tileName3 = tileName3[:-10]
                processing.run("gdal:cliprasterbymasklayer", {'INPUT':aiOutputReffedDirectory + tileName3 + 'TileReffed.tif','MASK':processBoundsSmallerDirectory + tileName3 + '.gpkg','SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':compressOptions,'DATA_TYPE':0,'EXTRA':'','OUTPUT':aiOutputRefClipDirectory3  + tileName3 + 'RefClipTile.tif'})
            print("Done pt.3")
        except BaseException as e:
            print (e)
            
    def four(task):
        try:
            for indivTile4 in reffedTilesNo4:
                tileName4 = indivTile4.split('\\')[-1]
                tileName4 = tileName4.split('.')[0]
                tileName4 = tileName4[:-10]
                processing.run("gdal:cliprasterbymasklayer", {'INPUT':aiOutputReffedDirectory + tileName4 + 'TileReffed.tif','MASK':processBoundsSmallerDirectory + tileName4 + '.gpkg','SOURCE_CRS':None,'TARGET_CRS':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':True,'OPTIONS':compressOptions,'DATA_TYPE':0,'EXTRA':'','OUTPUT':aiOutputRefClipDirectory4  + tileName4 + 'RefClipTile.tif'})
            print("Done pt.4")
        except BaseException as e:
            print (e)
        
    #Assign the functions to a Qgs task
    task1 = QgsTask.fromFunction('ClipperProcess', one)
    task2 = QgsTask.fromFunction('ItWorks2', two)
    task3 = QgsTask.fromFunction('ItWorks3', three)
    task4 = QgsTask.fromFunction('ItWorks4', four)

    #Combine and run the tasks
    task1.addSubTask(task2)
    task1.addSubTask(task3)
    task1.addSubTask(task4)
    QgsApplication.taskManager().addTask(task1)

    print("The tasks are now running in the background, you can check task manager for CPU usage")


    """
    #################################################################################################
    """

    #Wait for the clipping to finish...
    try:
        task1.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
    
    """
    #######################################################################
    """

    #Prepare to make a final mosaic where the alpha bands are respected
    finalImageDir = finalImageDir.replace("/", "\\")
    aiOutputRefClipDirectory1 = aiOutputRefClipDirectory1.replace("/", "\\")
    aiOutputRefClipDirectory2 = aiOutputRefClipDirectory2.replace("/", "\\")
    aiOutputRefClipDirectory3 = aiOutputRefClipDirectory3.replace("/", "\\")
    aiOutputRefClipDirectory4 = aiOutputRefClipDirectory4.replace("/", "\\")


    """
    #######################################################################
    """

    gdalOptionsSpeed = '-co COMPRESS=ZSTD -co PREDICTOR=1 -co NUM_THREADS=ALL_CPUS -co BIGTIFF=IF_SAFER -co TILED=YES -multi --config GDAL_NUM_THREADS ALL_CPUS -wo NUM_THREADS=ALL_CPUS -overwrite'
    gdalOptionsFinal = '-co COMPRESS=LZW -co PREDICTOR=2 -co NUM_THREADS=ALL_CPUS -co BIGTIFF=IF_SAFER -co TILED=YES -multi --config GDAL_NUM_THREADS ALL_CPUS -wo NUM_THREADS=ALL_CPUS -overwrite'
        

    def cmdOne(task):
        try:
            cmd = 'gdalwarp -of GTiff ' + gdalOptionsSpeed + ' -dstalpha "' + aiOutputRefClipDirectory1 + '**.tif" "' + stagingImageDir + outImageName + 'Staging1.tif" & timeout 5'
            os.system(cmd)
        except BaseException as e:
            print (e)

    cmdTask1 = QgsTask.fromFunction('CmdProcess', cmdOne)
    QgsApplication.taskManager().addTask(cmdTask1)

    def cmdTwo(task):
        try:
            cmd = 'gdalwarp -of GTiff ' + gdalOptionsSpeed + ' -dstalpha "' + aiOutputRefClipDirectory2 + '**.tif" "' + stagingImageDir + outImageName + 'Staging2.tif" & timeout 5'
            os.system(cmd)
        except BaseException as e:
            print (e)

    cmdTask2 = QgsTask.fromFunction('CmdProcess2', cmdTwo)
    QgsApplication.taskManager().addTask(cmdTask2)

    def cmdThree(task):
        try:
            cmd = 'gdalwarp -of GTiff ' + gdalOptionsSpeed + ' -dstalpha "' + aiOutputRefClipDirectory3 + '**.tif" "' + stagingImageDir + outImageName + 'Staging3.tif" & timeout 5'
            os.system(cmd)
        except BaseException as e:
            print (e)

    cmdTask3 = QgsTask.fromFunction('CmdProcess3', cmdThree)
    QgsApplication.taskManager().addTask(cmdTask3)

    def cmdFour(task):
        try:
            cmd = 'gdalwarp -of GTiff ' + gdalOptionsSpeed + ' -dstalpha "' + aiOutputRefClipDirectory4 + '**.tif" "' + stagingImageDir + outImageName + 'Staging4.tif" & timeout 5'
            os.system(cmd)
        except BaseException as e:
            print (e)

    cmdTask4 = QgsTask.fromFunction('CmdProcess4', cmdFour)
    QgsApplication.taskManager().addTask(cmdTask4)

    """
    #######################################################################
    """

    try:
        cmdTask1.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
            
    try:
        cmdTask2.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)

    try:
        cmdTask3.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)
        
    try:
        cmdTask4.waitForFinished(timeout = 20000000)
    except BaseException as e:
        print(e)

    """
    #######################################################################
    """

    #Final task
    cmd = 'gdalwarp -of GTiff ' + gdalOptionsFinal + ' "' + stagingImageDir + '**.tif" "' + finalImageDir + outImageName + datetime.now().strftime("%Y%m%d%H%M") + '.tif" & timeout 5'
    os.system(cmd)

    print("Ok look under " + finalImageDir)
    
else:
    print("Alright bro get those tiles to the AI upscaler")
    

"""
#######################################################################
"""

#All done
endTime = time.time()
totalTime = endTime - startTime
print("Done, this took " + str(int(totalTime)) + " seconds")


