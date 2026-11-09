HDF5 data structure: There are two tables:
    • Data0 (frequency 66.7 Hz)
	o	process_status: boolean variable indicating the start of welding. 
        o	pyrometer_back: temperature of the weld [°C] (consider flux is still present here) 
        o	pyrometer_R: temperature of the plate in the right zone [°C]
        o	pyrometer_L: temperature of the plate in the left zone [°C]
        o	wire_speed_a: wire feeding speed for dc electrode [m/min]
        o	wire_speed_b: wire feeding speed for AC electrode [m/min]
        o	x: cartesian variable of the weld [mm]
        o	y: cartesian variable of the weld [mm]
        o	z: cartesian variable of the weld [mm]
        o	timestamp: time associated with each point in unix time 
    • Data1 (frequency 5 kHz): 
        o	current_a: current of the dc electrode [A]
        o	current_b: current of the ac electrode [A]
        o	voltage_a: voltage of the dc electrode [V]
        o	voltage_b: voltage of the AC electrode [V]
        o	timestamp: time associated with each point in unix time

Open HDF5 files in HDF5 Viewer:
1. Download and Install HDFView (https://www.hdfgroup.org/downloads/hdfview/)
2. Open HDFView, then go to the File menu at the top and select Open. Choose the HDF5 file (.h5, .hdf5, .hdf) you want to open.
3. Once opened, you’ll see the file’s hierarchical structure in the Tree View on the left panel.
4. Click on datasets or groups to inspect their contents.
5. Double-click a dataset to open it in a table format.
6. Use the Tools menu to inspect metadata, attributes, and perform basic visualizations.


TXT files corresponds to data acquired from a profilometer, which captures surface profiles in three-dimensional space: 
    • x: position along the horizontal axis (scan direction) [mm]
    • y: position along the lateral axis (perpendicular to the scan direction) [mm]
    • z: height or depth of the measured surface at that point [mm]

Open txt files in Cloud Compare:
1. Open and launch CloudCompare on your computer.
2. Click File > Open and select your TXT file.
3. Click OK to import the data.
4. The imported data will appear in the data base tree (left panel).
5. Use the navigation tools to zoom, rotate, and inspect the point cloud.


Open NDE files in ShareCad:
1. Open ShareCAD online or on your computer
2. Click the Open button or drag and drop your NDE file into the viewer.
3. ShareCAD will automatically process and display the file.
4. Use the zoom, pan, and rotate tools to explore the file.
5. If the file contains multiple layers, you can toggle their visibility in the layer manager.
