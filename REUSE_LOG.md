# Changes to the reused DDR3 block

Source: juliancoy/zynqPCB, commit `5cb7c703` (NOTICE). The block is everything inside the `User.1` outline (PLAN.md §4.1).
Any change to its parts or copper goes here, with the reason and how it was checked. **Planned** entries are made
after the import (PLAN.md §4.2). **Done** entries name the commit.

| # | Status | Change | Why | Check |
|---|---|---|---|---|
| E1 | planned | **CK trunk (SoC → U16, In2 `SIGNAL1`):** add a coupled meander to the pair, plus extra length on CK_P only. Targets: **CK_P +4.30 mm (+28.5 ps), CK_N +3.23 mm (+21.4 ps)**, i.e. CK = DQS0 + 25 ps and CK P/N matched. Room: the straight runs at x = 165.2, y 125.6–130.5 (≈ 0.6 mm free per side) and y 117.9–120.4 (≈ 1 mm free per side), in source coordinates | UG933: CK ≥ DQS for every byte (write levelling). On JLC081611-7628 byte 0 is at **CK − DQS0 = 0.0 ps**. CK P/N is 7.1 ps (N leg 1.5 mm longer, which over-compensates the 2.9 ps package difference) | `tools/ddr3_review.py` on both DRAMs: byte 0 CK − DQS ≥ +20 ps, CK P/N ≤ 1 ps; A/C − CK stays inside ±123 ps (expected −24…+7 ps); DRC with our rules |
| E2 | planned, optional | DQS3_N +1.34 mm (+8.9 ps) on In2 | DQS3 P/N 8.9 ps, the largest pair skew in the block | as E1 |
| E3 | planned | U8 (TPS51200) EN: no longer from PS_MIO14 + 20 k to 3V3; tie to our power-good chain or a pull-up to our rail | keeps bank 500 free and at 1.8 V (the 20 k pull-up to 3V3 would back-drive a 1.8 V MIO) | ERC, netlist |
| E4 | planned | U15/U16 value MT41K256M16HA-125:E → MT41K256M16TW-107:P (same land) | HA-125 has 0 stock at JLC | footprint pads unchanged; courtyard for the 8 × 14 mm body |
