# -*- coding: utf-8 -*-
"""
Created on Mon Jul  3 18:20:48 2023

@author: YUNDAM
"""

import os

from eppy.modeleditor import IDF
from IDD.genIDD90 import genIDD
from eppy.runner.run_functions import runIDFs

from util import (triangulateEarclip, gen_zones, 
poly2roof, gen_horizontal_vertex, edge2wall, roof2wallNormVec, 
gen_WallProp, gen_WindowProp, gen_FloorName, gen_RoofName,
idf_zones, gen_zonelist, idf_walls, idf_windows, idf_roofs,
idf_floors, wall2window, set_Ins_thickness, set_glazing, get_epwinfo)

from pyproj import Proj, Transformer
from shapely import Polygon 
import shapely

class genEnergyPlus():
    
    def main(self, bldgID = '1', polygon = 'POLYGON ((127.0315587438314 37.501081104859935, 127.0314689735815 37.501054953642395, 127.03139605138767 37.50119293302112, 127.03149483600107 37.50122135252302, 127.0315587438314 37.501081104859935))', 
             wwr = 0.4, floorHeight = 3.5, uwall = 2.0, uroof = 2.0, ufloor = 2.0, uwindow = 3.5, 
             useType = 1, buildingHeight = 10.3, builtYear = 1990, light = 30, pv = 0.5, wsg84 = True, run_simulation = True, user_input = False):
        
        '''
        polygon = wkt 형식 str
            
        '''
        
        # 디렉토리 할당
        cpath = os.getcwd()  # 작업폴더 (current path)    
        MinimalIDFpath = os.path.join(cpath, 'IDF') # Minimal IDF 디렉토리
        iddpath = genIDD()
        IDF.setiddname(iddpath)
              
        # epwPath = './EPW/KOR_SO_Seoul.WS.471080_TMYx.2007-2021.epw'
        epwPath = os.path.join(cpath, 'EPW/KOR_SO_Seoul.WS.471080_TMYx.2007-2021.epw')
        # savePath = '.'
        
        epwFileName = epwPath.split(sep='\\')[-1]
        region, lat, lon, tzone, elev = get_epwinfo(epwPath)
        


        
        # Get the UTM Proj object
        utm_proj = get_utm_proj(latitude, longitude)
        
        # Define the source CRS (WGS 84)
        wgs84_proj = Proj(proj='latlong', datum='WGS84')
        
        # Create a transformer object
        transformer = Transformer.from_proj(wgs84_proj, utm_proj)
        
        # Transform the coordinates to the UTM CRS
        x, y = transformer.transform(latitude, longitude)
        print(f"Coordinates in UTM CRS: x={x}, y={y}")

        
        
        
        # 좌표 설정
        # target_crs = {'proj': 'tmerc', 'lat_0': 38, 'lon_0': 127.5, 'k': 0.9996, 'x_0': 1000000, 'y_0': 2000000, 'ellps': 'GRS80', 'units': 'm', 'no_defs': True} 
        #my_proj = Proj(target_crs)
        my_proj = Proj(proj='latlong', datum='WGS84')
        
        # Geometry 불러오기
        polygon = shapely.wkt.loads(polygon)
                
        # # Define a function to transform coordinates to a target projection
        # def transform_coordinates(lon, lat, target_proj):
        #     # Define the target projection
        #     target = Proj(target_proj)
        #     # Transform coordinates from WGS84 to the target projection
        #     x, y = transform(my_proj, target, lon, lat)
        #     return x, y

        if wsg84: # 좌표가 위경도인 데이터셋은 UTM으로 변환 필요
        
            targetBldgCoords = polygon.boundary.coords._coords
            
            xs = []
            ys = []
                
            for k in range(len(targetBldgCoords)):
             
                x, y = my_proj(targetBldgCoords[k][0], targetBldgCoords[k][1], inverse=False) # x, y
                
                xs.append(x)
                ys.append(y)
                
            polygon = Polygon([(xx, yy) for xx, yy in zip(xs, ys)])    
            
            cpath = os.getcwd() 
            MinimalIDFpath = os.path.join(cpath, 'IDF') 
        
        
        # IDF 파일명
        newIDF = 'Bldg_ID_' + str(bldgID) + '.idf'
        print('Generating... Baseline')
        
        n_floor = int(buildingHeight / floorHeight) # 지상층수
        
        # 준공연도에 따른 Minimal IDF 파일 선정 / 설계변수 선택
        
        if builtYear < 1980:
            minimalIDF = str(useType)+'1.idf'

        elif builtYear < 1990:
            minimalIDF = str(useType)+'2.idf'
            
        elif builtYear < 2000:
            minimalIDF = str(useType)+'3.idf'         
        
        elif builtYear < 2010:
            minimalIDF = str(useType)+'3.idf'
            
        else:
            minimalIDF = str(useType)+'4.idf'
        
        
        if user_input:
            
            pass
        
        else:
            
            if builtYear < 1980:
                
                uwall = 2.5
                uroof = 2.5
                ufloor = 2.5
                uwindow = 3.5
                light = 30
                
            elif builtYear < 1990:
                
                uwall = 2
                uroof = 2
                ufloor = 2
                uwindow = 3.0
                light = 25
                
            elif builtYear < 2000:
                
                uwall = 1.5
                uroof = 1.5
                ufloor = 1.5
                uwindow = 2.5
                light = 20
               
            
            elif builtYear < 2010:
                
                uwall = 1.0
                uroof = 1.0
                ufloor = 1.0
                uwindow = 2.0
                light = 15
                
            else:
                
                uwall = 0.5
                uroof = 0.5
                ufloor = 0.5
                uwindow = 1.5
                light = 10

        # Polygon 좌표 보정 (원점: 건물 중심)
        cent = polygon.centroid 
        bx, by = cent.x, cent.y 
        blon, blat = my_proj(bx, by, inverse = True) # 건물중심 위도 & 경도

        polygon = polygon.simplify(30) # Geometry 간소화
        
        # 대상건물 Polygon 삼각분할 (Ear-Clipping 알고리즘) -> EnergyPlus 형상 정보 관련 에러 방지
        # 오목평면 (concave plane) -> 볼록평면화 (convex planes)
        poly_triangulated = triangulateEarclip(polygon)
        
        
        # 대상건물 Zone 정보 생성 (zone 이름, zone 층고) -> zone XYZ 원점은 (0,0,0)
        zone_name, zone_height = gen_zones(n_floor, height = floorHeight)
        
        # 1층 지붕 외곽 Polygon (0. 삼각분할 이전, 1. 위에서 바닥을 바라보았을 때 반시계방향 회전, 2. 윗방향으로 층고만큼 offset)        
        RoofPolygon = poly2roof(polygon, floorHeight)  # 외벽 좌표 생성하는데 활용 -> 1층의 천장 높이의 좌표 점 List    
        # 바닥, 지붕 Polygon
        floors, roofs = gen_horizontal_vertex(poly_triangulated, n_floor, floorHeight) # 각 층의 바닥 및 천장 좌표 생성
        
        # # 아래 위 층의 천장 좌표 활용해서 외벽 Polygon 좌표 생성
        walls = [edge2wall(RoofPolygon[idx], RoofPolygon[idx+1])
                 if idx != len(RoofPolygon)-1 else edge2wall(RoofPolygon[idx], RoofPolygon[0]) 
                 for idx in range(len(RoofPolygon)) ]
        
        # 외벽 방위 (XY 좌표계에서 반시계방향 회전 기준, 법선각도 (degree), 법선벡터 (XY), 외벽 중심좌표 (3D))
        wallAng, wallNormVec = roof2wallNormVec(RoofPolygon) # 법선각도, 법선벡터
        
        # 창호 Polygon (외벽 Polygon & 창면적비 조합)   
        windows = [wall2window(wall, wwr = wwr) for wall in walls]  #WWR 고정
        
        
        ## 외피 IDF 속성정보 생성 (EnergyPlus)
        # Name: 외피이름
        # ZoneName: 매칭되는 zone 이름
        # BoundCond: 인접면 조건 (e.g. outdoors, surface)
        # SunExposure, WindExposure: 태양 및 바람 노출여부
        
        WallName, WallZoneName, WallBoundCond, WallBoundCondObj, WallSunExposure, WallWindExposure = gen_WallProp(walls, n_floor) # wall property name 입력
        WindowName, WindowSurType, WindowWallName, WindowBoundCondObj = gen_WindowProp(windows, n_floor) # window property name 입력
        FloorName, FloorZoneName, FloorBoundCond, FloorBoundCondObj, FloorSunExposure, FloorWindExposure = gen_FloorName(floors, n_floor) # floor property name 입력
        RoofName, RoofZoneName, RoofBoundCond, RoofBoundCondObj, RoofSunExposure, RoofWindExposure = gen_RoofName(roofs, n_floor) # roof property name 입력
        
        ## 벽 방위 저장
        # wall_info = {}
        # wall_info[bldg_idx] = (WallName, wallAng*n_floor) # 각도로 방위 판단하기 위함
        
        # 대상건물의 IDF 생성 - Baseline
        idf = IDF(os.path.join(MinimalIDFpath, minimalIDF), epw = epwFileName) # 할당된 idf 불러오기
        setattr(idf.idfobjects['BUILDING'][0], 'Solar_Distribution', 'FullExterior')
        
        idf = idf_zones(idf, zone_name, zone_height)
        idf = gen_zonelist(idf, zone_name)
        idf = idf_walls(idf, walls, WallName, WallBoundCond, WallBoundCondObj, WallSunExposure, WallWindExposure, WallZoneName, floorHeight)        
        idf = idf_windows(idf, windows, WindowName, WindowSurType, WindowWallName, WindowBoundCondObj, floorHeight)
        idf = idf_roofs(idf, roofs, RoofName, RoofBoundCond, RoofBoundCondObj, RoofSunExposure, RoofWindExposure, RoofZoneName)    
        idf = idf_floors(idf, floors, FloorName, FloorBoundCond, FloorBoundCondObj, FloorSunExposure, FloorWindExposure, FloorZoneName)   
        
        idf = set_Ins_thickness(idf, uwall, uroof, ufloor)
        idf = set_glazing(idf, uwindow)
        
        
        # 조명 에너지 설정
        setattr(idf.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', light)
        
        # this_savepath = os.path.join(savepath, EPWRegion)
        idfSavePath = os.path.join('.', newIDF)
        idf.saveas(idfSavePath)
        


        if user_input:
                
            
            if run_simulation: 
            
                # print('Running... ' + newIDF)
                # idf.run(output_prefix = 'Bldg_ID_' + bldgID, output_suffix = 'L', readvars=True, output_directory = cpath, ep_version="9-0-1")        
                print('Generating... Options')
                
                # 대상건물의 IDF 생성 - Green
                idf_green = IDF(idfSavePath, epw = epwFileName)
                
                # 단열 설정
                idf_green = set_Ins_thickness(idf_green, 0.1, 0.1, 0.1)
                idf_green = set_glazing(idf_green, 1.0)
                
                # 조명 에너지 설정
                setattr(idf_green.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', light)
                
                # this_savepath = os.path.join(savepath, EPWRegion)
                idfGreenSavePath = os.path.join('.', newIDF[:-4] + '_green_' + '.idf')
                idf_green.saveas(idfGreenSavePath)

                
                # 대상건물의 IDF 생성 - Greener
                idf_greener = IDF(idfGreenSavePath, epw = epwFileName)
                
                # 단열 설정
                idf_greener = set_Ins_thickness(idf_greener, 0.1, 0.1, 0.1)
                idf_greener = set_glazing(idf_greener, 1.0)
                
                # 조명 에너지 설정
                setattr(idf_greener.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', 3)
                
                # this_savepath = os.path.join(savepath, EPWRegion)
                idfGreenerSavePath = os.path.join('.', newIDF[:-4] + '_greener_' + '.idf')
                idf_greener.saveas(idfGreenerSavePath)
                    
                # 대상건물의 IDF 생성 - Greenest
                idf_greenest = IDF(idfGreenerSavePath, epw = epwFileName)
                
                # 단열 설정
                idf_greenest = set_Ins_thickness(idf_greenest, 0.1, 0.1, 0.1)
                idf_greenest = set_glazing(idf_greenest, 1.0)
                
                # 조명 에너지 설정
                setattr(idf_greenest.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', 3)
                
                # this_savepath = os.path.join(savepath, EPWRegion)
                idfGreenestSavePath = os.path.join('.', newIDF[:-4] + '_greenest_' + '.idf')
                idf_greenest.saveas(idfGreenestSavePath)
                
                if run_simulation: # multi-processing 
                
                    print('Running...')

                    options_baseline = {'output_prefix':'Bldg_ID_' + bldgID, 
                                  "output_suffix":'L',
                                  "readvars":True,
                                  "output_directory":cpath,
                                  "ep_version":"9-0-1"}
                    
                    options_green = {'output_prefix':newIDF[:-4] + '_green_', 
                                  "output_suffix":'L',
                                  "readvars":True,
                                  "output_directory":cpath,
                                  "ep_version":"9-0-1"}

                    options_greener = {'output_prefix':newIDF[:-4] + '_greener_', 
                                  "output_suffix":'L',
                                  "readvars":True,
                                  "output_directory":cpath,
                                  "ep_version":"9-0-1"}
                    
                    options_greenest = {'output_prefix':newIDF[:-4] + '_greenest_', 
                                  "output_suffix":'L',
                                  "readvars":True,
                                  "output_directory":cpath,
                                  "ep_version":"9-0-1"}
                                    
                    runs = [[idf, options_baseline], [idf_green, options_green], [idf_greener, options_greener], [idf_greenest, options_greenest]]
                    runIDFs(runs, 4) # 0: use all CPUs, -1: one less than all CPUs, 1~: number of CPUs
            else:
                
                pass
        
        else:
            
            print('Generating... Options')
            
            # 대상건물의 IDF 생성 - Green
            idf_green = IDF(idfSavePath, epw = epwFileName)
            
            # 단열 설정
            idf_green = set_Ins_thickness(idf_green, 0.1, 0.1, 0.1)
            idf_green = set_glazing(idf_green, 1.0)
            
            # 조명 에너지 설정
            setattr(idf_green.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', light)
            
            # this_savepath = os.path.join(savepath, EPWRegion)
            idfGreenSavePath = os.path.join('.', newIDF[:-4] + '_green_' + '.idf')
            idf_green.saveas(idfGreenSavePath)

            
            # 대상건물의 IDF 생성 - Greener
            idf_greener = IDF(idfGreenSavePath, epw = epwFileName)
            
            # 단열 설정
            idf_greener = set_Ins_thickness(idf_greener, 0.1, 0.1, 0.1)
            idf_greener = set_glazing(idf_greener, 1.0)
            
            # 조명 에너지 설정
            setattr(idf_greener.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', 3)
            
            # this_savepath = os.path.join(savepath, EPWRegion)
            idfGreenerSavePath = os.path.join('.', newIDF[:-4] + '_greener_' + '.idf')
            idf_greener.saveas(idfGreenerSavePath)
                
            # 대상건물의 IDF 생성 - Greenest
            idf_greenest = IDF(idfGreenerSavePath, epw = epwFileName)
            
            # 단열 설정
            idf_greenest = set_Ins_thickness(idf_greenest, 0.1, 0.1, 0.1)
            idf_greenest = set_glazing(idf_greenest, 1.0)
            
            # 조명 에너지 설정
            setattr(idf_greenest.idfobjects['LIGHTS'][0], 'Watts_per_Zone_Floor_Area', 3)
            
            # this_savepath = os.path.join(savepath, EPWRegion)
            idfGreenestSavePath = os.path.join('.', newIDF[:-4] + '_greenest_' + '.idf')
            idf_greenest.saveas(idfGreenestSavePath)
            
            if run_simulation: # multi-processing 
            
                print('Running...')

                options_baseline = {'output_prefix':'Bldg_ID_' + bldgID, 
                              "output_suffix":'L',
                              "readvars":True,
                              "output_directory":cpath,
                              "ep_version":"9-0-1"}
                
                options_green = {'output_prefix':newIDF[:-4] + '_green_', 
                              "output_suffix":'L',
                              "readvars":True,
                              "output_directory":cpath,
                              "ep_version":"9-0-1"}

                options_greener = {'output_prefix':newIDF[:-4] + '_greener_', 
                              "output_suffix":'L',
                              "readvars":True,
                              "output_directory":cpath,
                              "ep_version":"9-0-1"}
                
                options_greenest = {'output_prefix':newIDF[:-4] + '_greenest_', 
                              "output_suffix":'L',
                              "readvars":True,
                              "output_directory":cpath,
                              "ep_version":"9-0-1"}
                                
                runs = [[idf, options_baseline], [idf_green, options_green], [idf_greener, options_greener], [idf_greenest, options_greenest]]
                runIDFs(runs, 4) # 0: use all CPUs, -1: one less than all CPUs, 1~: number of CPUs
                
            
        print('!!! Done !!!')

        # copy2(os.path.join(epwpath, EPWFname), os.path.join(this_savepath, EPWFname))

        

