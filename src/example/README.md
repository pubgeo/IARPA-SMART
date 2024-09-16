# Test Harness Example Inputs and Outputs

Example data inputs to the test harness are saved in [input](input). Example output files from two separate test harness runs are saved in [output.compare](output.compare).

- From `src` directory
- Check [example\example_run.sh](example\example_run.sh) and update `REPO` variable to point to root directory of code repo
- Run [example\example_run.sh](example\example_run.sh) and compare the generated "output" folder to [output.compare](output.compare)
- Verify correct output by comparing generated output to expected output: <br>Generated output: `example/output/KR_R002/overall/bas/scoreboard_rho=0.5.csv` <br>Expected output: [example/output.compare/KR_R002/overall/bas/scoreboard_rho=0.5.csv](output.compare/KR_R002/overall/bas/scoreboard_rho=0.5.csv) 
- This comparison can be done using the `diff` command. <br>i.e. `diff example/output.compare/KR_R002/overall/bas/scoreboard_rho=0.5.csv example/output/KR_R002/overall/bas/scoreboard_rho=0.5.csv`

