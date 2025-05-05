### This script is just for class Project in ECE260C 
### It reads the sdc file and 3_3_place_gp.odb file
### Then performs buffering and timing optimization for addressing ERC violations
# You can run this script in this manner:  openroad -python python_check_ERC_violations.py

import sys
import argparse
import pdn, odb, utl
from openroad import Tech, Design, Timing
import openroad as ord
import time
from pathlib import Path
import os
import re


def load_design(techNode, floorplanOdbFile, sdcFile):
  tech = Tech()
  platform_dir = "./platforms/" + techNode + "/"
  libDir = Path(platform_dir + "lib/")
  lefDir = Path(platform_dir + "lef/")
  rcFile = platform_dir + "setRC.tcl"

  print("libDir: ", libDir)
  print("lefDir: ", lefDir)
  print("rcFile: ", rcFile)

  # Read technology files
  libFiles = libDir.glob('*.lib')
  lefFiles = lefDir.glob('*.lef')
  for libFile in libFiles:
    print("Reading library file: %s\n" % libFile)
    tech.readLiberty(libFile.as_posix())
  
  techLefFiles = lefDir.glob("*tech*.lef")
  for techLefFile in techLefFiles:
    tech.readLef(techLefFile.as_posix())
  for lefFile in lefFiles:
    tech.readLef(lefFile.as_posix())
  
  design = Design(tech)

  # read the odb file
  design.readDb(floorplanOdbFile)
  design.evalTclString("read_sdc %s"%sdcFile)
  design.evalTclString("source " + rcFile)

  return tech, design


def get_connection(large_net_threshold, file_name, IO_map, inst_map):
  f = open(file_name, "a")
  f.write("Nets information (Each line represents one net. The first element in each line is the driver pin.):\n")
  block = ord.get_db_block()
  nets = block.getNets()
  for net in nets:
    if net.getName() == "VDD" or net.getName() == "VSS":
      continue
    if (len(net.getITerms()) + len(net.getBTerms()) >= large_net_threshold):
      continue

    sinkPins = []
    driverId = -1
    dPin = None
    # check the instance pins
    for p in net.getITerms():
      if p.isOutputSignal():
        dPin = p
        driverId = inst_map[p.getInst().getName()]
      else:
        sinkPins.append(inst_map[p.getInst().getName()])
    
    # check the IO pins
    for p in net.getBTerms():
      if dPin is None and p.getIoType() == "INPUT":
        dPin = p
        driverId = IO_map[p.getName()]
      else:
        sinkPins.append(IO_map[p.getName()])
      
    if dPin is None:
      if (net.getName() == "VDD" or net.getName() == "VSS"):
        continue  # ignore power and ground nets
      print("No driver found for net: ",net.getName())
      continue
   
    if (len(sinkPins) + 1 >= large_net_threshold):
      print("Ignore large net: ",net.getName())
      continue

    if (len(sinkPins) == 0):
      continue

    f.write(str(driverId) + " ")
    for sinkId in sinkPins:
      f.write(str(sinkId) + " ")
    f.write("\n")
  f.write("*********************************************************************************************\n")
  f.close()


def get_registers(design):
    registers = []
    regs_ptr = design.evalTclString("::sta::all_register").split()
    for reg in regs_ptr:
        reg_db_ptr = design.evalTclString("::sta::sta_to_db_inst "+reg)
        if reg_db_ptr != "NULL":
            reg_inst_name = design.evalTclString(reg_db_ptr+" getName")
            registers.append(reg_inst_name)
    return registers


def get_clknets(design):
    clk_nets = []
    clk_nets_ptr = design.evalTclString("::sta::find_all_clk_nets").split()
    clk_nets = [design.evalTclString(x+" getName") for x in clk_nets_ptr]
    return clk_nets


def get_insts(design, inst_map, file_name, vertex_id):
  block = ord.get_db_block()
  insts = block.getInsts()
  registers = get_registers(design)
  f = open(file_name, "a")
  f.write("Instance information (Each line represents one instance: vertex_id, instance_name, cell_name, isMacro, isSeq, isFixed, x_center, y_center, width, height):\n")
  for inst in insts:
    instName = inst.getName()
    master = inst.getMaster()
    masterName = master.getName()
    BBox = inst.getBBox()
    isMacro = master.isBlock()
    isSeq = True if instName in registers else False
    isFixed = True if inst.isFixed() else False
    lx = BBox.xMin()
    ly = BBox.yMin()
    ux = BBox.xMax()
    uy = BBox.yMax()
    width = ux - lx
    height = uy - ly
    x_center = (lx + ux) / 2
    y_center = (ly + uy) / 2
    isFiller = True if master.isFiller() else False
    isTapCell = True if ("TAPCELL" in masterName or "tapcell" in masterName) else False
    #isBuffer = 1 if design.isBuffer(master) else 0
    #isInverter = 1 if design.isInverter(master) else 0
    if (isFiller == True or isTapCell == True):
      continue # ignore filler and tap cells
    f.write(str(vertex_id) + " ")
    f.write(instName + " ")
    f.write(masterName + " ")
    f.write(str(isMacro) + " ")
    f.write(str(isSeq) + " ")
    f.write(str(isFixed) + " ")
    if (isMacro == True or isFixed == True):
      f.write(str(x_center) + " ")
      f.write(str(y_center) + " ")
    else:
      f.write(str(-1) + " ")
      f.write(str(-1) + " ")
    f.write(str(width) + " ")
    f.write(str(height) + " ")
    f.write("\n")
    inst_map[instName] = vertex_id
    vertex_id += 1
  f.write("*********************************************************************************************\n")
  f.close()     


### This function is only for testing purpose
### Please replace this function with your own function
def generate_init_placement(design, file_name):
  f = open(file_name, "w")
  block = ord.get_db_block()
  insts = block.getInsts()
  registers = get_registers(design)
  for inst in insts:
    instName = inst.getName()
    master = inst.getMaster()
    masterName = master.getName()
    BBox = inst.getBBox()
    isMacro = master.isBlock()
    isSeq = True if instName in registers else False
    isFixed = True if inst.isFixed() else False
    lx = BBox.xMin()
    ly = BBox.yMin()
    ux = BBox.xMax()
    uy = BBox.yMax()
    width = ux - lx
    height = uy - ly
    x_center = (lx + ux) / 2
    y_center = (ly + uy) / 2
    isFiller = True if master.isFiller() else False
    isTapCell = True if ("TAPCELL" in masterName or "tapcell" in masterName) else False
    #isBuffer = 1 if design.isBuffer(master) else 0
    #isInverter = 1 if design.isInverter(master) else 0
    if (isFiller == True or isTapCell == True):
      continue # ignore filler and tap cells
    f.write(instName + " ")
    if (isMacro == True or isFixed == True):
      continue
    else:
      f.write(str(int(x_center)) + " ")
      f.write(str(int(y_center)) + " ")
    f.write("\n")
  f.close()     




def load_init_placement(file_name):
  with open(file_name, "r") as f:
    content = f.read().splitlines()
  f.close()

  block = ord.get_db_block()
  for line in content:
    items = line.split(" ")
    if len(items) < 3:
      continue

    instName = items[0]
    x = int(float(items[1]))
    y = int(float(items[2]))

    # Set the position of the instance    
    inst = block.findInst(instName)
    inst.setLocation(x, y)


def run_incremental_placement(design):
  # Configure and run global placement
  print("###run global placement###")
  design.evalTclString("global_placement -routability_driven -timing_driven -skip_initial_place -incremental")

  print("Please use the generated 3_3_place_gp.def and 3_3_place_gp.odb files for remaining flows.")
  design.writeDef("3_3_place_gp.def")
  design.writeDb("3_3_place_gp.odb")

  # Run initial detailed placement
  site = design.getBlock().getRows()[0].getSite()
  max_disp_x = int((design.getBlock().getBBox().xMax() - design.getBlock().getBBox().xMin()) / site.getWidth())
  max_disp_y = int((design.getBlock().getBBox().yMax() - design.getBlock().getBBox().yMin()) / site.getHeight())
  print("The following files are just for testing purpose. Please ignore them.")
  print("###run legalization###")
  design.getOpendp().detailedPlacement(max_disp_x, max_disp_y, "")
  
  design.writeDef("3_5_place_dp.def")
  design.writeDb("3_5_place_dp.odb")


def write_design(design, file_name):
  design.writeDef(file_name + ".def")
  design.writeDb(file_name + ".odb")

def get_IO_pins(IO_map, file_name):
  f = open(file_name, "a")
  f.write("Input/Output Pin information (Each line represents one fixed pin: vertex_id, IO_name, IO_type, x_center, y_center):\n")
  block = ord.get_db_block()
  BTerms = block.getBTerms()
  vertex_id = 0
  for bTerm in BTerms:
    BBox = bTerm.getBBox()
    x_center = (BBox.xMin() + BBox.xMax()) / 2
    y_center = (BBox.yMin() + BBox.yMax()) / 2
    f.write(str(vertex_id) + " ")
    f.write(bTerm.getName() + " ")
    f.write(bTerm.getIoType() + " ")
    f.write(str(int(x_center)) + " ")
    f.write(str(int(y_center)) + "\n")
    IO_map[bTerm.getName()] = vertex_id
    vertex_id += 1
  f.write("*********************************************************************************************\n")
  f.close()



def get_dbu():
  block = ord.get_db_block()
  dbunits = block.getDbUnitsPerMicron()
  return dbunits


def get_basic_info(file_name):
  block = ord.get_db_block()
  design_name = block.getName()
  dbunits = block.getDbUnitsPerMicron()
  die_width = block.getDieArea().dx() 
  die_height = block.getDieArea().dy() 
  core_width = block.getCoreArea().dx() 
  core_height = block.getCoreArea().dy() 
  nets = block.getNets()
  insts = block.getInsts()

  f = open(file_name, "a")
  f.write("*********************************************************************************************\n")
  f.write("Basic information of the design:\n")
  f.write("Design name: %s\n"%design_name)
  #f.write("Number of nets: %d\n"%len(nets))
  #f.write("Number of instances: %d\n"%len(insts))
  f.write("UNITS DISTANCE MICRONS : %d (We use DBU to store the layout information)\n"%dbunits)  
  f.write("Die width: %d DBU\n"%die_width)
  f.write("Die height: %d DBU\n"%die_height)
  f.write("Core width: %d DBU\n"%core_width)
  f.write("Core height: %d DBU\n"%core_height)
  f.write("Core region:  lx = %d, ly = %d, ux = %d, uy = %d\n"%(block.getCoreArea().xMin(),
                                                            block.getCoreArea().yMin(),
                                                            block.getCoreArea().xMax(),
                                                            block.getCoreArea().yMax()))
  f.write("*********************************************************************************************\n")
  f.close()



# check the cap violations
def get_electricial_violation(sta, driver_pin, cap_margin = 0.0):
  liberty_cell_pin = None
  
  for MTerm in driver_pin.getInst().getMaster().getMTerms():
    if (driver_pin.getInst().getName() + "/" + MTerm.getName()) == driver_pin.getName():
      liberty_cell_pin = MTerm      
      break    


  if liberty_cell_pin is None:
    print("No liberty cell pin found for driver pin: ", driver_pin.getName())
    return 0

  maxCap = sta.getMaxCapLimit(liberty_cell_pin)
  print("Max cap limit for driver pin: ", driver_pin.getName(), " is ", maxCap)

  maxTrans = sta.getMaxSlewLimit(liberty_cell_pin)
  print("Max transition limit for driver pin: ", driver_pin.getName(), " is ", maxTrans)
    
  # get the slew
  slew = sta.getPinSlew(driver_pin)
  print("Slew for driver pin: ", driver_pin.getName(), " is ", slew)

  corner = sta.getCorners()[0]
  net = driver_pin.getNet()
  if net is not None:
    for pin in net.getITerms():
      print("Pin name: ", pin.getName())
      if pin.isInputSignal():
        input_cap = sta.getPortCap(pin, corner, sta.Max)
        print("Input cap for sink pin: ", pin.getName(), " is ", input_cap)

def check_ERC_violation(sta, design, max_fanout = None):
  slew_viol_count = 0
  cap_viol_count = 0
  max_fanout_viol_count = 0
  corner = sta.getCorners()[0]
  
  for pin in design.getBlock().getITerms():
    if pin.getNet() == None:
      continue
      
    driver_pin = pin # driver pin
    net = driver_pin.getNet()
    if net.getSigType() == 'POWER' or net.getSigType() == 'GROUND' or net.getSigType() == 'CLOCK':
      continue

    if re.match(".*/SETN$", driver_pin.getName()) or re.match(".*/RESETN$", driver_pin.getName()) :
      continue

    liberty_cell_pin = None  
    for MTerm in driver_pin.getInst().getMaster().getMTerms():
      if (driver_pin.getInst().getName() + "/" + MTerm.getName()) == driver_pin.getName():
        liberty_cell_pin = MTerm      
        break    

    if liberty_cell_pin is None:
      print("No liberty cell pin found for driver pin: ", driver_pin.getName())
      return 0

    # check slew violations
    if sta.getMaxSlewLimit(liberty_cell_pin) < sta.getPinSlew(driver_pin):
      slew_viol_count += 1

    # check cap violations
    # flute or wireload is used in STA to estimate the capacitance
    if sta.getMaxCapLimit(liberty_cell_pin) < sta.getNetCap(driver_pin.getNet(), corner, sta.Max):
      cap_viol_count += 1

    # check max fanout violations 
    if max_fanout is not None:
      if len(net.getITerms()) > max_fanout:
        max_fanout_viol_count += 1
        print("Max fanout violation for driver pin: ", driver_pin.getName(), " is ", len(driver_pin.getNet().getITerms()))

  print("Slew violations: ", slew_viol_count)
  print("Capacitance violations: ", cap_viol_count)
  print("Max fanout violations: ", max_fanout_viol_count)



# Function to insert a buffer cell by breaking a given net
# Specify the buffer cell type and the net to be buffered
# The buffer list we are using: BUF_X1， BUF_X2, BUF_X4, BUF_X8, BUF_X16
# lx, ly are the lower left coordinates of the buffer cell to be inserted
# lx and ly should be specified in DBU (database units)
# You can use get_dbu() to get the dbu value
# return 0 means no buffer is inserted
# return 1 means buffer is inserted
def insert_buffer(sta, net_name, buf_cell_type, inserted_buffer_count, lx = -1, ly = -1) -> int:
  db = ord.get_db()
  block = ord.get_db_block()  
  source_net = block.findNet(net_name)
  
  # identify the source pin  
  driver_pin = None
  power_net = None
  gnd_net = None
  
  for pin in source_net.getITerms():
    if pin.isOutputSignal():
      driver_pin = pin
      break

  if driver_pin is not None:
    driver_inst = driver_pin.getInst()
    for pin in driver_inst.getITerms():
      if pin.getSigType() == 'POWER':
        power_net = pin.getNet()
      elif pin.getSigType() == 'GROUND':
        gnd_net = pin.getNet()
    if (lx == -1 or ly == -1):
      # if the coordinates are not specified, place the buffer cell at the center of the driver pin
      bbox = driver_inst.getBBox()
      lx = int((bbox.xMin() + bbox.xMax()) / 2)
      ly = int((bbox.yMin() + bbox.yMax()) / 2)     


  if driver_pin is None:
    # check the IO pins 
    for io_pin in source_net.getBTerms():
      if driver_pin is None and io_pin.getIoType() == "INPUT":
        driver_pin = io_pin
        break

  if power_net is None and gnd_net is None:
    sink_inst = source_net.getITerms()[0].getInst()
    for pin in sink_inst.getITerms():
      if pin.getSigType() == 'POWER':
        power_net = pin.getNet()
      elif pin.getSigType() == 'GROUND':
        gnd_net = pin.getNet()
    if (lx == -1 or ly == -1):
      # if the coordinates are not specified, place the buffer cell at the center of the sink pin
      bbox = sink_inst.getBBox()
      lx = int((bbox.xMin() + bbox.xMax()) / 2)
      ly = int((bbox.yMin() + bbox.yMax()) / 2)


  if driver_pin is None:
    print("No driver pin found for net: ", net_name)
    return 0

  if power_net is None and gnd_net is None:
    print("No power or ground net found for net: ", net_name)
    return 0

  master = db.findMaster(buf_cell_type)
  if master is None:
    print("Buffer cell type not found: ", buf_cell_type)
    return 0  

  # Create a new instance of the buffer cell
  new_inst = odb.dbInst_create(block, master, 'inserted_buffer_' + str(inserted_buffer_count))  
  # Set the orientation and position of the new instance
  new_inst.setOrient('R0')
  new_inst.setPlacementStatus('PLACED')
  new_inst.setLocation(lx, ly)
  print("Inserting buffer cell: ", buf_cell_type, " at (", lx, ",", ly, ") in net ", net_name) 
  
  # Create a new net
  new_net = odb.dbNet_create(block, 'inserted_buffer_net_' + str(inserted_buffer_count))
  driver_pin.disconnect()
  driver_pin.connect(new_net)
  
  # Connect the pins of the new instance
  for pin in new_inst.getITerms():
    if pin.isInputSignal():
      pin.connect(new_net)
    elif pin.isOutputSignal():
      pin.connect(source_net)
    elif pin.getSigType() == 'POWER':
      pin.connect(power_net)
    elif pin.getSigType() == 'GROUND':
      pin.connect(gnd_net)

  #check_cap_violation(sta, driver_pin)

  return 1


if __name__ == "__main__":
    # You can run this script in this manner:  openroad -python python_read_design.py
    parser = argparse.ArgumentParser(description="Example script to perform timing optimization using OpenROAD.")
    parser.add_argument("-d", default="ibex", help="Give the design name")
    parser.add_argument("-t", default="nangate45", help="Give the technology node")
    parser.add_argument("-large_net_threshold", default="1000", help="Large net threshold. We should remove global nets like reset.")
    
    args = parser.parse_args()

    tech_node = args.t
    design = args.d
    large_net_threshold = int(args.large_net_threshold)
    hg_file_name = str(design) + "_" + str(tech_node) + ".txt"
    f = open(hg_file_name, "w")
    f.close()

    path = "./results/" + tech_node + "/" + design + "/base"
    gp_place_odb_file = path + "/3_3_place_gp.odb"
    sdc_file = path + "/2_floorplan.sdc"
    # Load the design
    tech, design = load_design(tech_node, gp_place_odb_file, sdc_file)
    sta = Timing(design)

    inserted_buffer_count = 0
    
    #net_name = "_03537_"
    net_name = "instr_addr_o[29]"

    buf_cell_type = "BUF_X1"
    inserted_buffer_count += insert_buffer(sta, net_name, buf_cell_type, inserted_buffer_count)

    write_design(design, "update_buffer")

    check_ERC_violation(sta, design)