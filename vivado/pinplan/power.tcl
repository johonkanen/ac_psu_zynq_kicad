# Vivado power estimate of the pin-plan design (PS7 as configured + PL I/O + static), for POWER_BUDGET.md.
# Run from vivado/pinplan/build after pinplan.py:  vivado -mode batch -source ../power.tcl
# Copy build/power_summary.csv to vivado/pinplan/ to record a result.
# Rail sizing at a fixed junction temperature (typical / maximum process), and the thermal cases with the junction
# left to Vivado (still air, 8-layer board).
open_checkpoint placed.dcp
set f [open power_summary.csv w]
puts $f "case,process,ambient_C,junction_C,heatsink,total_W,static_W,tja_CW,vccint_A,vccaux_A,vccbram_A,vccpint_A,vccpaux_A,vccpll_A,vcco_ddr_A,vcco_mio0_A,vcco_mio1_A,vccadc_A,vcco33_A"
proc row {f name proc amb tj hs {tja -}} {
  set args [list -process $proc -airflow 0 -board small -board_layers 8to11 -heatsink $hs]
  if {$tja ne "-"} { lappend args -thetaja $tja }
  if {$tj ne "-"} { lappend args -junction_temp $tj } else { lappend args -ambient_temp $amb }
  reset_operating_conditions
  set_operating_conditions {*}$args
  report_power -file power_$name.rpt
  set t [read [open power_$name.rpt]]
  regexp {Total On-Chip Power \(W\)\s*\|\s*([\d.]+)} $t -> tot
  regexp {Device Static \(W\)\s*\|\s*([\d.]+)} $t -> st
  regexp {Junction Temperature \(C\)\s*\|\s*([\d.]+)} $t -> j
  if {![regexp {Effective TJA \(C/W\)\s*\|\s*([\d.]+)} $t -> tja]} { set tja - }
  set out "$name,$proc,$amb,$j,$hs,$tot,$st,$tja"
  foreach r {Vccint Vccaux Vccbram Vccpint Vccpaux Vccpll Vcco_ddr Vcco_mio0 Vcco_mio1 Vccadc Vcco33} {
    regexp "\\| $r +\\|\[^|\]+\\|\\s*(\[\\d.\]+)" $t -> a
    append out ",$a"
  }
  puts $f $out
}
row $f size_typ_tj85  typical - 85 none
row $f size_max_tj85  maximum - 85 none
row $f size_max_tj100 maximum - 100 none
row $f th_typ_40      typical 40 - none
row $f th_typ_60      typical 60 - none
row $f th_max_40      maximum 40 - none
# theta-JA set directly: 22 C/W for the bare 76 x 65 mm card (smaller than Vivado's 4" x 4" board, 17.3 C/W),
# 10 C/W with a small BGA heatsink (estimates, to be confirmed by measurement)
row $f th_typ_50_bare typical 50 - none 22
row $f th_typ_60_bare typical 60 - none 22
row $f th_max_50_bare maximum 50 - none 22
row $f th_typ_60_hs   typical 60 - none 10
row $f th_max_60_hs   maximum 60 - none 10
row $f th_max_70_hs   maximum 70 - none 10
close $f
