from qgis.core import *
import qgis.utils
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.gui import *
import processing
import numpy as np
import os.path
from jenks import jenks

#Stuff to add:
#Supoort for sqlite after resolving performance issues
#Check that mif file works
#Jenks classification through CYTHON code
#Add automatic support for MAC - change of // direction

def AddNormalizedColumn(eLayer, newColumn):
    caps = eLayer.dataProvider().capabilities()
    count = eLayer.dataProvider().fieldNameIndex(newColumn)
    if caps & QgsVectorDataProvider.DeleteAttributes:
        res =eLayer.dataProvider().deleteAttributes([count])
    eLayer.updateFields()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = eLayer.dataProvider().addAttributes([QgsField(newColumn, QVariant.Double)])
    eLayer.updateFields()
    return

def calcNormIntegration(eLayer, formerColumn, newColumn):   
    index = eLayer.fieldNameIndex(newColumn)
    valList = eLayer.getValues(formerColumn)[0]
    maxAttrVal = np.max(valList)
    print maxAttrVal, index
    for feature in eLayer.getFeatures():
        #print "chvalue", feature[formerColumn]/maxAttrVal
        #eLayer.dataProvider().changeAttributeValues({feature.id() : {eLayer.dataProvider().fieldNameMap()[newColumn] : np.float(feature[formerColumn]/maxAttrVal)}})
        eLayer.changeAttributeValue(feature.id() , index, np.float(feature[formerColumn]/maxAttrVal))
    return

def normalizeIntegration(preLayer, postLayer, radii =["n", "250", "500", "750", "1000", "1250", "1500", "2000", "2500", "3000"]):
    
    for rad in radii:
        AddNormalizedColumn(preLayer, "pr"+rad)
        AddNormalizedColumn(postLayer, "po"+rad)
    
    preLayer.startEditing()
    for rad in radii:
        calcNormIntegration(preLayer, rad, "pr"+rad)
    preLayer.commitChanges()
    
    postLayer.startEditing()
    for rad in radii:
        calcNormIntegration(postLayer, rad, "po"+rad)
    postLayer.commitChanges()

    return

def addImpColumn(joinedLayer, impName):
    caps = joinedLayer.dataProvider().capabilities()
    count = joinedLayer.dataProvider().fieldNameIndex(impName)
    if caps & QgsVectorDataProvider.DeleteAttributes:
        res =joinedLayer.dataProvider().deleteAttributes([count])
    joinedLayer.updateFields()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = joinedLayer.dataProvider().addAttributes([QgsField(impName, QVariant.Double)])
    joinedLayer.updateFields()
    return
    
def calculateRatio(joinedLayer, preColumn, postColumn, impColumn, notChoice):
    index = joinedLayer.fieldNameIndex(impColumn)
    if notChoice:
        for feature in joinedLayer.getFeatures():
            joinedLayer.changeAttributeValue(feature.id() , index, np.float(feature[postColumn]/feature[preColumn]))
    else:
        for feature in joinedLayer.getFeatures():
            joinedLayer.changeAttributeValue(feature.id() , index, np.float((feature[postColumn]+1)/(feature[preColumn]+1)))
    return

    
def printImage(joinedLayer, rad):
    img = QImage(QSize(800, 600), QImage.Format_ARGB32_Premultiplied)
    color = QColor(255, 255, 255) 
    img.fill(color.rgb())
    p = QPainter() 
    p.begin(img) 
    p.setRenderHint(QPainter.Antialiasing)
    renderer = QgsMapRenderer()
    lst = [joinedLayer.id()] 
    renderer.setLayerSet(lst)
    rect = QgsRectangle(renderer.fullExtent()) 
    rect.scale(1.1) 
    renderer.setExtent(rect)
    renderer.setOutputSize(img.size(), img.logicalDpiX())
    renderer.render(p)
    p.end()
    res=img.save("C:\\Users\\yoav\\Copy\\LLPlanners\\PythonScripts\\SpaceSyntaxDiff\\imp"+rad+"PosNeg.png","png")
    print res
    return

def quantile(values, classes=5):
  """
  Quantum GIS quantile algorithm in Python
  
  Returns values taken at regular intervals from the cumulative 
  distribution function (CDF) of 'values'.
  """

  values.sort()
  n = len(values)
  breaks = []
  for i in range(classes):
    q = i / float(classes)
    a = q * n
    aa = int(q * n)
    r = a - aa
    Xq = (1 - r) * values[aa] + r * values[aa+1]
    breaks.append(Xq)
  breaks.append(values[n-1])
  return breaks

def visPosNeg(joinedLayer, radii=["n", "250", "500", "750", "1000", "1250", "1500", "2000", "2500", "3000"]):
    
    orangeColor = QColor("#ff6200")
    whiteColor = QColor("#ffffff")
    greenColor = QColor("#4cdd4c")
    
    ss1Color = QColor("#192aa0")
    ss2Color = QColor("#3f7df4")
    ss3Color = QColor("#40d7ac")
    ss4Color = QColor("#48fd32")
    ss5Color = QColor("#fef338")
    ss6Color = QColor("#fec531")
    ss7Color = QColor("#fd942a")
    ss8Color = QColor("#fd8945")
    ss9Color = QColor("#fc3e42")
    
    for rad in radii:
        newJoinedLayer = iface.addVectorLayer(joinedLayer.source(), joinedLayer.name()+rad, "ogr")
        if not newJoinedLayer: 
            print "layer failed to load!"
        
        impAttrName = "imp"+rad
        impValues = newJoinedLayer.getValues(impAttrName)[0]
        [minValAttr, lowerQuantile, upperQuantile, maxValAttr] = quantile(impValues, 3)
        
        print minValAttr, lowerQuantile, upperQuantile, maxValAttr
        
        posNegRanges = (
        ("Negative", minValAttr, lowerQuantile, orangeColor),
        ("Neutral", lowerQuantile, upperQuantile, whiteColor),
        ("Positive", upperQuantile, maxValAttr, greenColor),
        )

        ranges = []
        for label, lower, upper, color in posNegRanges:
            symbol = QgsSymbolV2.defaultSymbol(newJoinedLayer.geometryType())
            symbol.setColor(color)
            rng = QgsRendererRangeV2(lower, upper, symbol, label)
            ranges.append(rng)
            
        renderer = QgsGraduatedSymbolRendererV2(impAttrName, ranges)
        newJoinedLayer.setRendererV2(renderer)
        newJoinedLayer.triggerRepaint() 
        #printImage(joinedLayer, rad)
    
        newJoinedLayer = iface.addVectorLayer(joinedLayer.source(), joinedLayer.name()+rad+"ss", "ogr")
        if not newJoinedLayer: 
            print "layer failed to load!"

        ssValues = [i for i in impValues if i >1]
        ssBreaks = jenks(ssValues, 9)
        ssRanges = (
        ("ss1", ssBreaks[0], ssBreaks[1], ss1Color),
        ("ss2", ssBreaks[1], ssBreaks[2], ss2Color),
        ("ss3", ssBreaks[2], ssBreaks[3], ss3Color),
        ("ss4", ssBreaks[3], ssBreaks[4], ss4Color),
        ("ss5", ssBreaks[4], ssBreaks[5], ss5Color),
        ("ss6", ssBreaks[5], ssBreaks[6], ss6Color),
        ("ss7", ssBreaks[6], ssBreaks[7], ss7Color),
        ("ss8", ssBreaks[7], ssBreaks[8], ss8Color),
        ("ss9", ssBreaks[8], ssBreaks[9], ss9Color),
        )
        
        ranges = []
        for label, lower, upper, color in ssRanges:
            symbol = QgsSymbolV2.defaultSymbol(newJoinedLayer.geometryType())
            symbol.setColor(color)
            rng = QgsRendererRangeV2(lower, upper, symbol, label)
            ranges.append(rng)
            
        renderer = QgsGraduatedSymbolRendererV2(impAttrName, ranges)
        newJoinedLayer.setRendererV2(renderer)
        newJoinedLayer.triggerRepaint()
        #jenks cythoin implementation links
        #http://quantumofgis.blogspot.co.il/2014/11/qgis-standalone-and-python-modules.html
        #install git and put it in the PATH: http://git-scm.com/downloads
        #get visual c++ from http://aka.ms/vcpython27
        #https://github.com/perrygeo/jenks
        #[ssmin, ss1, ..., ssmax] = jenks(ssValues, 9)
    
    layers = iface.legendInterface().layers()
    for layer in layers:
        iface.legendInterface().setLayerVisible(layer, False)
    
    iface.legendInterface().setLayerVisible(joinedLayer, True)
    if hasattr(joinedLayer, "setCacheImage"):
        joinedLayer.setCacheImage(None) 
    joinedLayer.triggerRepaint()    
    return

def ssdiff(fullJoinedLayerFileName, joinedLayerFileName, radii =["n", "250", "500", "750", "1000", "1250", "1500", "2000", "2500", "3000"], notChoice=True):
    joinedLayer = iface.addVectorLayer(fullJoinedLayerFileName, "joinedLayer", "ogr")
    if not joinedLayer: 
        print fullJoinedLayerFileName+"Layer failed to load!"
    
    for rad in radii:
        addImpColumn(joinedLayer, "imp"+rad)
    
    joinedLayer.startEditing()
    for rad in radii:
        calculateRatio(joinedLayer, "pr"+rad, "po"+rad, "imp"+rad, notChoice)
    joinedLayer.commitChanges()
    
    visPosNeg(joinedLayer, radii)
    return

def rundiff(preLayerFileName, postLayerFileName, joinedLayerFileName="joinedLayer", radii =["n", "250", "500", "750", "1000", "1250", "1500", "2000", "2500", "3000"], notChoice=True):
    QgsMapLayerRegistry.instance().removeAllMapLayers()    
    preLayer = iface.addVectorLayer(preLayerFileName, "preLayer", "ogr")
    if not preLayer: 
        print "Layer failed to load!"
    
    postLayer = iface.addVectorLayer(postLayerFileName, "postLayer", "ogr")
    if not postLayer: 
        print "Layer failed to load!"
    
    normalizeIntegration(preLayer, postLayer, radii)
    
    workSource = iface.activeLayer().source()
    workDir = os.path.dirname(workSource)
    newJoinedLayerFileName = workDir + "//" + joinedLayerFileName + ".shp"
    processing.runalg("qgis:joinattributesbylocation", preLayer, postLayer, u'equals', 5.00, 0, 'sum', 0, newJoinedLayerFileName)
    
    ssdiff(newJoinedLayerFileName, joinedLayerFileName, radii, notChoice) 
    
    return
    


