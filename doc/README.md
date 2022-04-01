Available commands can be found in the token_str const of [statemachine.c](/src/statemachine.c). To issue the STATUS command, send "!STATUS" via UDP to stationd. [Stationd.pdf](https://github.com/oresat/uniclogs-hardware/tree/master/eb-ground-station/power-system/Stationd.pdf) mentioned below is good for understanding some of the command flows. For example, after starting stationd, sending "!PWR_ON" will move you from the initial PwrUp state block to the PwrOn state block. At any time, "!KILL" will power everything down and move you back to the PwrUp state. Sadly, Stationd.pdf is out of date, missing the RX only flows and some notable changes to commands have been made ("Power-on" -> "PWR_ON", etc). Commands are not case sensitive. No help command is provided.

Specific to the OreSat ground station, "!PWR_ON" will turn on accessories like the webcam, in addition to the rotator and SDR SBC. For testing receive operations, "!RX" will bring up the LNA without the TX amps. From there, you can send your polarization command of choice.

## See active documentation in the repo:

[oresat/uniclogs-hardware/eb-ground-station/power-system](https://github.com/oresat/uniclogs-hardware/tree/master/eb-ground-station/power-system)

* Station_Board.txt
* Stationd.pdf
* power_bits.txt

