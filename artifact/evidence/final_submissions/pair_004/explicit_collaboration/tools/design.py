"""
UGS-SYNTH-D01 v1.1 - proposed design definition.

Coordinates are site plan-view metres.  Piece numbering:
  INJ-*  compressor units (the one bank serves both services)
  HDR-*  headers / manifolds              SEP/DEHY treatment trains
  MTR/REG metering, regulation            DRN-* closed drains
Pipeline classes/diameters are catalog identifiers from piping_catalog.json.
"""

from engine import C, Design

# ---------------------------------------------------------------- constants
WG_IDS = ['WG-01', 'WG-02', 'WG-03', 'WG-04', 'WG-05', 'WG-06']
WG_Y = {'WG-01': 45.0, 'WG-02': 117.0, 'WG-03': 189.0,
        'WG-04': 261.0, 'WG-05': 333.0, 'WG-06': 405.0}
WG_X = 12.0

CLS_WET = 'CS-WET-160'      # wet service, 16 MPa rating
CLS_DRY = 'CS-DRY-160'      # dry service, 16 MPa rating
CLS_DRN = 'CS-WET-100'      # liquid-drain compatible class

ROAD_W = 6.0
ROAD_MAIN_Y = 225.0
ROAD_NS_X = 421.0
ROAD_TREAT_X = 478.0

# withdrawal inlet pressure control: protects the C40 suction limit (12 MPa)
INLET_PC_SETPOINT_MPA = 11.5


def build():
    d = Design()

    # ------------------------------------------------------------- equipment
    # compressor bank (north-west process area) - serves injection and withdrawal
    d.add('INJ-C1', 'C60', 398.0, 400.0, 0)
    d.add('INJ-C2', 'C60', 398.0, 355.0, 0)
    d.add('INJ-C3', 'C40', 400.0, 315.0, 0)
    d.add('HDR-A', 'HDR120', 345.0, 380.0, 0)     # compressor suction manifold
    d.add('HDR-B', 'HDR120', 470.0, 380.0, 0)     # compressor discharge manifold
    d.add('COOL', 'COOL120', 530.0, 380.0, 0)     # injection aftercooler
    # grid side
    d.add('MTR-INJ', 'MTR120', 640.0, 300.0, 90)
    d.add('MTR-WDR', 'MTR120', 640.0, 245.0, 90)
    d.add('REG-WDR', 'REG120', 640.0, 190.0, 90)
    d.add('HDR-F', 'HDR120', 605.0, 190.0, 0)     # treated gas product manifold
    # well manifold
    d.add('HDR-C', 'HDR120', 340.0, 245.0, 0)
    d.add('HDR-E', 'HDR120', 470.0, 178.0, 0)     # treatment feed manifold
    # treatment trains (3 x parallel, identical)
    for i, y in ((1, 250.0), (2, 195.0), (3, 140.0)):
        d.add('SEP-%d' % i, 'SEP70', 490.0, y, 0)
        d.add('DEHY-%d' % i, 'DEHY70', 555.0, y, 0)
    # closed drains
    for i, y in ((1, 115.0), (2, 105.0), (3, 95.0)):
        d.add('DRN-%d' % i, 'DRN-S', 540.0, y, 0)

    # ------------------------------------------------------------- pipelines
    def P(pid, frm, to, dn, cls, pts, lvls=None, service='gas'):
        if lvls is None:
            lvls = ['ground'] * (len(pts) - 1)
        d.add_pipe(pid, frm, to, dn, cls, pts, lvls, service=service)

    iface = lambda i: ('IFACE:%s' % i, 'gas')

    # ---- grid tie: one inlet metering line, one outlet metering line
    P('P01', iface('GRID-TIE'), ('MTR-INJ', 'gas_in'), 'DN700', CLS_DRY,
      [(700.0, 225.0), (660.0, 225.0), (660.0, 298.0), (640.0, 298.0)])
    P('P02', ('MTR-INJ', 'gas_out'), ('HDR-A', 'branch_03'), 'DN700', CLS_DRY,
      [(640.0, 302.0), (640.0, 308.0), (346.5, 308.0), (346.5, 378.5)])
    # ---- compressor suction
    P('P03', ('HDR-A', 'branch_09'), ('INJ-C1', 'suction'), 'DN500', CLS_WET,
      [(347.0, 381.5), (347.0, 400.0), (390.5, 400.0)])
    P('P04', ('HDR-A', 'branch_07'), ('INJ-C2', 'suction'), 'DN500', CLS_WET,
      [(343.5, 378.5), (343.5, 355.0), (390.5, 355.0)])
    P('P05', ('HDR-A', 'branch_10'), ('INJ-C3', 'suction'), 'DN300', CLS_WET,
      [(348.0, 379.0), (360.0, 379.0), (360.0, 315.0), (394.0, 315.0)])
    # ---- compressor discharge
    P('P06', ('INJ-C1', 'discharge'), ('HDR-B', 'branch_08'), 'DN500', CLS_WET,
      [(405.5, 400.0), (432.0, 400.0), (432.0, 380.75), (467.0, 380.75)])
    P('P07', ('INJ-C2', 'discharge'), ('HDR-B', 'branch_04'), 'DN500', CLS_WET,
      [(405.5, 355.0), (430.0, 355.0), (430.0, 379.25), (467.0, 379.25)])
    P('P08', ('INJ-C3', 'discharge'), ('HDR-B', 'branch_07'), 'DN300', CLS_WET,
      [(406.0, 315.0), (434.0, 315.0), (434.0, 378.5), (468.5, 378.5)])
    P('P09', ('HDR-B', 'branch_06'), ('COOL', 'gas_in'), 'DN600', CLS_DRY,
      [(473.0, 380.0), (524.0, 380.0)])
    P('P10', ('COOL', 'gas_out'), ('HDR-C', 'branch_10'), 'DN600', CLS_DRY,
      [(536.0, 380.0), (548.0, 380.0), (343.0, 244.0)])
    # ---- well flowlines (shared by both services)
    branch_ports = {'WG-01': 'branch_07', 'WG-02': 'branch_03', 'WG-03': 'branch_04',
                    'WG-04': 'branch_08', 'WG-05': 'branch_05', 'WG-06': 'branch_01'}
    for i, wg in enumerate(WG_IDS, start=1):
        port = branch_ports[wg]
        a = d.equipment['HDR-C'].port_xy(port)
        P('P%02d' % (10 + i), ('HDR-C', port), iface(wg), 'DN300', CLS_WET, [a, (WG_X, WG_Y[wg])])
    # ---- withdrawal inlet path: well manifold -> inlet pressure control -> suction header
    P('L1', ('HDR-C', 'branch_09'), ('HDR-A', 'branch_04'), 'DN500', CLS_WET,
      [(342.0, 246.5), (342.0, 265.0), (320.0, 265.0), (320.0, 379.0), (342.0, 379.25)])
    # ---- withdrawal discharge path: discharge header -> treatment feed manifold
    P('L2', ('HDR-B', 'branch_03'), ('HDR-E', 'branch_05'), 'DN500', CLS_WET,
      [(471.5, 378.5), (471.5, 360.0), (470.0, 360.0), (470.0, 179.5)])
    # ---- treatment trains
    P('P21', ('HDR-E', 'branch_02'), ('SEP-1', 'gas_in'), 'DN300', CLS_WET,
      [(473.0, 179.0), (486.0, 250.0)])
    P('P22', ('HDR-E', 'branch_06'), ('SEP-2', 'gas_in'), 'DN300', CLS_WET,
      [(473.0, 178.0), (486.0, 195.0)])
    P('P23', ('HDR-E', 'branch_10'), ('SEP-3', 'gas_in'), 'DN300', CLS_WET,
      [(473.0, 177.0), (486.0, 140.0)])
    P('P24', ('SEP-1', 'gas_out'), ('DEHY-1', 'gas_in'), 'DN300', CLS_WET,
      [(494.0, 250.0), (550.0, 250.0)])
    P('P25', ('SEP-2', 'gas_out'), ('DEHY-2', 'gas_in'), 'DN300', CLS_WET,
      [(494.0, 195.0), (550.0, 195.0)])
    P('P26', ('SEP-3', 'gas_out'), ('DEHY-3', 'gas_in'), 'DN300', CLS_WET,
      [(494.0, 140.0), (550.0, 140.0)])
    P('P27', ('DEHY-1', 'gas_out'), ('HDR-F', 'branch_07'), 'DN300', CLS_WET,
      [(560.0, 250.0), (575.0, 250.0), (575.0, 188.5), (603.5, 188.5)])
    P('P28', ('DEHY-2', 'gas_out'), ('HDR-F', 'branch_04'), 'DN300', CLS_WET,
      [(560.0, 195.0), (568.0, 195.0), (568.0, 189.25), (602.0, 189.25)])
    P('P29', ('DEHY-3', 'gas_out'), ('HDR-F', 'branch_01'), 'DN300', CLS_WET,
      [(560.0, 140.0), (580.0, 140.0), (580.0, 191.5), (603.0, 191.5)])
    # ---- delivery to grid tie
    P('P30', ('HDR-F', 'branch_06'), ('REG-WDR', 'gas_in'), 'DN500', CLS_WET,
      [(608.0, 190.0), (620.0, 190.0), (620.0, 187.5), (640.0, 187.5)])
    P('P31', ('REG-WDR', 'gas_out'), ('MTR-WDR', 'gas_in'), 'DN500', CLS_WET,
      [(640.0, 192.5), (640.0, 243.0)])
    P('P32', ('MTR-WDR', 'gas_out'), iface('GRID-TIE'), 'DN500', CLS_WET,
      [(640.0, 247.0), (700.0, 247.0), (700.0, 225.0)])
    # ---- liquid drains
    P('P36', ('SEP-1', 'liquid_out'), ('DRN-1', 'drain_in'), 'DN200', CLS_DRN,
      [(490.0, 248.0), (515.0, 248.0), (515.0, 115.0), (539.0, 115.0)],
      service='liquid_drain')
    P('P37', ('SEP-2', 'liquid_out'), ('DRN-2', 'drain_in'), 'DN200', CLS_DRN,
      [(490.0, 193.0), (520.0, 193.0), (520.0, 105.0), (539.0, 105.0)],
      service='liquid_drain')
    P('P38', ('SEP-3', 'liquid_out'), ('DRN-3', 'drain_in'), 'DN200', CLS_DRN,
      [(490.0, 138.0), (525.0, 138.0), (525.0, 95.0), (539.0, 95.0)],
      service='liquid_drain')
    P('P39', ('DRN-1', 'drain_out'), iface('LIQUID-DRAIN-OUTFALL'), 'DN200', CLS_DRN,
      [(541.0, 115.0), (680.0, 115.0), (680.0, 120.0)], service='liquid_drain')
    P('P40', ('DRN-2', 'drain_out'), iface('LIQUID-DRAIN-OUTFALL'), 'DN200', CLS_DRN,
      [(541.0, 105.0), (670.0, 105.0), (670.0, 120.0), (680.0, 120.0)],
      service='liquid_drain')
    P('P41', ('DRN-3', 'drain_out'), iface('LIQUID-DRAIN-OUTFALL'), 'DN200', CLS_DRN,
      [(541.0, 95.0), (655.0, 95.0), (655.0, 130.0), (680.0, 130.0), (680.0, 120.0)],
      service='liquid_drain')

    # ------------------------------------------------------------------ roads
    d.road_centre_lines.append(('R1', [(ROAD_W / 2.0, ROAD_MAIN_Y), (660.0, ROAD_MAIN_Y)], ROAD_W))
    d.road_centre_lines.append(('R2', [(ROAD_NS_X, 100.0), (ROAD_NS_X, 440.0)], ROAD_W))
    d.road_centre_lines.append(('R3', [(ROAD_NS_X, 120.0), (665.0, 120.0)], ROAD_W))
    d.road_centre_lines.append(('R4', [(ROAD_TREAT_X, 110.0), (ROAD_TREAT_X, 275.0)], ROAD_W))
    return d


# ---------------------------------------------------------------- operation
BRANCH_PIPE = {'WG-01': 'P11', 'WG-02': 'P12', 'WG-03': 'P13',
               'WG-04': 'P14', 'WG-05': 'P15', 'WG-06': 'P16'}
# pipe paths of the three parallel treatment trains (identical models)
TRAIN_PATHS = {'1': ('P21', 'P24', 'P27'), '2': ('P22', 'P25', 'P28'),
               '3': ('P23', 'P26', 'P29')}
TRAIN_FIXED_DP_MPA = {'1': 0.03 + 0.08, '2': 0.03 + 0.08, '3': 0.03 + 0.08}
# liquid side streams: separator liquid_out line and drain_out line of each train
TRAIN_LIQ_PIPES = {'1': ('P36', 'P39'), '2': ('P37', 'P40'), '3': ('P38', 'P41')}
