### This script is just for Project #2 in CSE291A class
### It reads the sdc file and 3_2_place_iop.odb file
### Then convert the design into a hypergraph
### Then read global placement solution back and run the global placement incrementally
### Then perform legalization and detailed placement

import sys
import argparse
import pdn, odb, utl
from openroad import Tech, Design, Timing
import openroad as ord
import time
from pathlib import Path


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

def get_connection(large_net_threshold):
  block = ord.get_db_block()
  nets = block.getNets()
  for net in nets:
    sinkPins = []
    dPin = None
    # check the instance pins
    for p in net.getITerms():
      if p.isOutputSignal():
        dPin = p
      else:
        sinkPins.append(p)
    
    # check the IO pins
    for p in net.getBTerms():
      if dPin is None:
        dPin = p
      else:
        sinkPins.append(p)
      
    if dPin is None:
      print("No driver found for net: ",net.getName())
      continue
   
    if (len(sinkPins) >= large_net_threshold):
      print("Ignore large net: ",net.getName())
      continue

    print("Driver: ",dPin.getName())
    for p in sinkPins:
      print("Sink: ",p.getName())
    print('\n')




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


def get_insts(design):
  block = ord.get_db_block()
  insts = block.getInsts()
  registers = get_registers(design)
  
  for inst in insts:
    instName = inst.getName()
    master = inst.getMaster()
    masterName = master.getName()
    BBox = inst.getBBox()
    isMacro = master.isBlock()
    isSeq = 1 if instName in registers else 0
    isFixed = 1 if inst.isFixed() else 0
    lx = BBox.xMin()
    ly = BBox.yMin()
    ux = BBox.xMax()
    uy = BBox.yMax()
    isFiller = 1 if master.isFiller() else 0
    isTapCell = 1 if ("TAPCELL" in masterName or "tapcell" in masterName) else 0
    isBuffer = 1 if design.isBuffer(master) else 0
    isInverter = 1 if design.isInverter(master) else 0

    if (isFiller == 1 or isTapCell == 1):
      print("master name : ", masterName, " lx = ", lx, " ly = ", ly, " ux = ", ux, " uy = ", uy)


def get_basic_info():
  block = ord.get_db_block()
  design_name = block.getName()
  dbunits = block.getDbUnitsPerMicron()
  die_width = block.getDieArea().dx() / dbunits
  die_height = block.getDieArea().dy() / dbunits
  core_width = block.getCoreArea().dx() / dbunits
  core_height = block.getCoreArea().dy() / dbunits
  nets = block.getNets()
  insts = block.getInsts()

  print("*********************************************************")
  print("Basic information of the design:")
  print("Design name: ", design_name)
  print("Die width: %d um"%die_width)
  print("Die height: %d um"%die_height)
  print("Core width: %d um"%core_width)
  print("Core height: %d um"%core_height)
  print("Number of nets: ", len(nets))
  print("Number of instances: ", len(insts))
  print("UNITS DISTANCE MICRONS : ", dbunits)  
  print("*********************************************************")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Example script to perform global placement initialization using OpenROAD.")
    parser.add_argument("-d", default="ibex", help="Give the design name")
    parser.add_argument("-t", default="nangate45", help="Give the technology node")
    parser.add_argument("-large_net_threshold", default="1000", help="Large net threshold. We should remove global nets like reset.")
    
    args = parser.parse_args()

    tech_node = args.t
    design = args.d
    large_net_threshold = int(args.large_net_threshold)

    path = "./results/" + tech_node + "/" + design + "/base"
    floorplan_odb_file = path + "/3_2_place_iop.odb"
    sdc_file = path + "/2_floorplan.sdc"

    # Load the design
    tech, design = load_design(tech_node, floorplan_odb_file, sdc_file)

    # Get basic information
    #get_basic_info()

    # get all the connections
    #get_connection(large_net_threshold)      
    
    # get all the instances
    get_insts(design)










