import re
import time
import subprocess
import argparse
import requests
import json
import sys
import urllib3
import os



def grep(input, keyword):
    li = input.splitlines()
    for line in li:
        if (str(keyword) in line):
            output = line
    return output


def get_rmip_and_slot(): 
    if os.name == 'nt':
        file_path = r"C:\host_data.json"
    else:
        file_path = "/tmp/host_data.json"
    with open(file_path, "r") as f:
        lines = f.readlines()
        for item in lines:
            if "server_id" in item:
                server_id = item

    server_id = server_id.strip().replace('"', '').replace("server_id: ", "")
    url="http://local-console.localdomain/console/host_engine.php"
    data={"server_id": server_id, "action": "get_host_workflow_data"}
    response = requests.post(url, json=data, verify=False)
    response_dict = response.json()
    #print(response.status_code)
    t=response_dict["pdu_ports"]
    t=t.split(':')
    ip = str(t[0])
    slot = str(t[1])
    return ip, slot


#  #username = 'root'
# #password = '$pl3nd1D'

def run_curl_command(url, req_type):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if req_type == "get":
        try:
            response = requests.get(url, auth=('root', '$pl3nd1D'), verify=False)
            response_dict = response.json()
            #print(response.status_code)
            #print(json.dumps(response_dict, indent=4, sort_keys=True))
            return response_dict
            #return 0
        except Exception as e:
            print("\n An error occured: \n", e)
            return 1
    if req_type == "post":
        try:
            response = requests.post(url, data="{}" ,auth=('root', '$pl3nd1D'), verify=False)
            response_dict = response.json()
            #print(response.status_code)
            #print(json.dumps(response_dict, indent=4, sort_keys=True))
            return response_dict
        except Exception as e:
            print("\n An error occured: \n", e)
            return 1        

def main():
    parser = argparse.ArgumentParser(description='Redfish command for Venera UBB')
    parser.add_argument('--ip', help='Rack Manger IP Address', required=False)
    parser.add_argument('--slot', type=int, help='Rack Manger Slot Number',required=False)
    parser.add_argument('--no_ip', action='store_true', default=False, help='Get RM IP and Slot info from Console',required=False)
    #parser.add_argument('--bmcip',  default="", help='BMC IP Address')
    #parser.add_argument('--logdir', default=default_logdir, type=str, help="default: %(default)s")
    #parser.add_argument('--stdout', action='store_true', default=False, help="Use stdout instead of log files")
    #parser.add_argument('--smcselftest', action='store_true', default=False, help="Perform smc self test")
    parser.add_argument('--ubbfru', action='store_true', default=False, help="Collects UBB FRU")
    parser.add_argument('--smcsensors', action='store_true', default=False, help="Collect SMC Sensors")
    parser.add_argument('--smclog', action='store_true', default=False, help="Perform SMC log entries and clear log actions")
    parser.add_argument('--cper', action='store_true', default=False, help="Perform SMC CPER Dump")
    parser.add_argument('--journalctl', action='store_true', default=False, help="Perform SMC journalctl Dump")
    #parser.add_argument('--smcreset', action='store_true', default=False, help="Perform SMC reset")
    parser.add_argument('--fwversions', action='store_true', default=False, help="Capture the firmware versions")

    args = parser.parse_args()   
    exit_code=0

    if len(sys.argv)==1:
        parser.print_help()
        # parser.print_usage() # for just the usage line
        print("\nex: python3", sys.argv[0], "--ip 10.231.31.6 --slot 1 --smclog")
        print("ex: python3", sys.argv[0], "--no_ip --smclog \n")
        parser.exit()

    #check if --no_ip was used to get data from HOST-engine on console
    if args.no_ip:
        ip, slot = get_rmip_and_slot()

    if type(args.ip) == str and type(args.slot) == int:
        ip=args.ip
        slot=args.slot
    
    if args.smclog:
        #get SMC log
        url="https://{}:8080/{}/hmc/redfish/v1/Systems/UBB/LogServices/EventLog/Entries".format(ip , slot)
        response_dict = run_curl_command(url, "get")
        print(json.dumps(response_dict, indent=4, sort_keys=True))

        #check SMC logs for errors
        keywords = ["Error", "Failure", "Critical"]
        for member in response_dict['Members']:
            for keyword in keywords:
                if keyword in member['Message'] or \
                    keyword in member['MessageArgs'] or \
                    keyword in member['MessageId'] or \
                    keyword in member['Severity']:
                    exit_code=1
                    break
                else:
                    if not exit_code==1:
                        exit_code=0
        if exit_code!=0:
            print("\nFAIL: There are Errors in SMC Logs \n")
        else:
            print("\nPASS: There are no errors in SMC Log \n")
        #clear SMC log
        url="https://{}:8080/{}/hmc/redfish/v1/Systems/UBB/LogServices/EventLog/Actions/LogService.ClearLog".format(ip , slot)
        print("\nClearing SMC LOG \n")
        run_curl_command(url, "post")
        return exit_code
    if args.fwversions:
        fw_list=["rot_active", "amc_active" , "amc_fpga_active", "ubb_fpga_active" \
                 , "ifwi_active", "retimer_active", "rmi_active", "vr_bundle_active" \
                 , "bundle_active"]
        print(" ")
        for currdev in fw_list:  
            url="https://{}:8080/{}/hmc/redfish/v1/UpdateService/FirmwareInventory/{}".format(ip , slot, currdev)
            response_dict = run_curl_command(url, "get")
            try:
                print(response_dict['Id'] + ' : Version : ' + response_dict['Version'])
                print(response_dict['Id'] + ' : ComponentDetails : ' + response_dict['Oem']['VersionID']['ComponentDetails'])
                print("\n")
            except Exception as e:
                print("'Version' is not a key for this object \n", e)
    if args.ubbfru:
        sourceFile = open('ubb_fru.txt', 'a')
        print("####Starting OAM & UBB FRU reading#########################", file=sourceFile)
        fru_list=["OAM_0", "OAM_1", "OAM_2", "OAM_3", "OAM_4", "OAM_5", "OAM_6", "OAM_7"]
        for currdev in fru_list:  
            url="https://{}:8080/{}/hmc/redfish/v1/Chassis/{}".format(ip , slot, currdev)
            response_dict = run_curl_command(url, "get")
            print("OAM_Name: " + response_dict["Name"] + "\nPartNumber:" +
                  str(response_dict["PartNumber"]) + "\nSerialNumber:" + response_dict["SerialNumber"] \
				  + "\n", file=sourceFile)
            print(json.dumps(response_dict, indent=4, sort_keys=True))
        url="https://{}:8080/{}/hmc/redfish/v1/Chassis/UBB".format(ip , slot)
        response_dict = run_curl_command(url, "get")
        print("Name:" + response_dict["Name"] + "\nModel:" + response_dict["Model"] + "\nPartNumber" +
              response_dict["PartNumber"] + "\nUBB Serial Number:" + response_dict["SerialNumber"] \
			  + "\n", file=sourceFile)
        print(json.dumps(response_dict, indent=4, sort_keys=True))
        print("####Completed OAM & UBB FRU reading########################", file=sourceFile)

    if args.smcsensors:
        sensor_list=["UBB/Sensors/UBB_TEMP_FRONT", "UBB/Sensors/UBB_TEMP_BACK"  \
                , "OAM_0/Sensors/GPU_0_DIE_TEMP", "OAM_1/Sensors/GPU_1_DIE_TEMP" \
                , "OAM_2/Sensors/GPU_2_DIE_TEMP", "OAM_3/Sensors/GPU_3_DIE_TEMP" \
                , "OAM_4/Sensors/GPU_4_DIE_TEMP", "OAM_5/Sensors/GPU_5_DIE_TEMP" \
                , "OAM_6/Sensors/GPU_6_DIE_TEMP", "OAM_7/Sensors/GPU_7_DIE_TEMP" \
                , "OAM_0/Sensors/GPU_WARMEST_DIE_TEMP", "OAM_0/Sensors/GPU_0_MEMORY_TEMP" \
                , "OAM_1/Sensors/GPU_1_MEMORY_TEMP", "OAM_2/Sensors/GPU_2_MEMORY_TEMP" \
                , "OAM_3/Sensors/GPU_3_MEMORY_TEMP", "OAM_4/Sensors/GPU_4_MEMORY_TEMP" \
                , "OAM_5/Sensors/GPU_5_MEMORY_TEMP", "OAM_6/Sensors/GPU_6_MEMORY_TEMP" \
                , "OAM_6/Sensors/GPU_6_MEMORY_TEMP" \
                , "OAM_0/Sensors/GPU_WARMEST_MEMORY_TEMP", "OAM_0/Sensors/GPU_0_POWER" \
                , "OAM_1/Sensors/GPU_1_POWER", "OAM_2/Sensors/GPU_2_POWER", "OAM_3/Sensors/GPU_3_POWER" \
                , "OAM_4/Sensors/GPU_4_POWER", "OAM_5/Sensors/GPU_5_POWER", "OAM_6/Sensors/GPU_6_POWER" \
                , "OAM_7/Sensors/GPU_7_POWER", "OAM_0/Sensors/GPU_TOTAL_POWER" \
                , "UBB_FPGA/Sensors/UBB_FPGA_TEMP", "UBB/Sensors/UBB_TEMP_OAM7" \
                , "UBB/Sensors/UBB_TEMP_IBC", "UBB/Sensors/UBB_TEMP_UFPGA", "UBB/Sensors/UBB_TEMP_OAM1" \
                , "RETIMER_0/Sensors/RETIMER_0_TEMP", "RETIMER_1/Sensors/RETIMER_1_TEMP" \
                , "RETIMER_2/Sensors/RETIMER_2_TEMP", "RETIMER_3/Sensors/RETIMER_3_TEMP" \
                , "RETIMER_4/Sensors/RETIMER_4_TEMP", "RETIMER_5/Sensors/RETIMER_5_TEMP" \
                , "RETIMER_6/Sensors/RETIMER_6_TEMP", "RETIMER_7/Sensors/RETIMER_7_TEMP" \
                , "RETIMER_0/Sensors/RETIMER_MAX_TEMP", "UBB/Sensors/IBC_TEMP" \
                , "UBB/Sensors/IBC_HSC_TEMP", "OAM_0/Sensors/GPU_WARMEST_HSC_TEMP" \
                , "UBB/Sensors/UBB_POWER"]
        for currdev in sensor_list:  
            url="https://{}:8080/{}/hmc/redfish/v1/Chassis/{}".format(ip , slot, currdev)
            response_dict = run_curl_command(url, "get")
            try:
                print(response_dict['Id'] + ' : ' + str(response_dict['Reading']))
            except Exception as e:
                print("'Reading' is not a key for this object \n", e)

    if args.cper:
        # Run the GetAllCPER task
        print("\n****Running GetALLCPER Task**** \n")
        url="https://{}:8080/{}/hmc/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/Oem/LogService.GetAllCPER".format(ip , slot)
        response_dict = run_curl_command(url, "post")
        print(response_dict)
        #get task id
        task_id = response_dict['@odata.id']
        task_id = task_id[2:]

        time.sleep(10)  #should wait till ask 100%

        #get task info and entry location
        print("\n****Getting CPER Entry Location**** \n")
        url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
        response_dict = run_curl_command(url, "get")
        PercentComplete = response_dict["PercentComplete"]
        while PercentComplete != 100:
            url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
            response_dict = run_curl_command(url, "get")
            PercentComplete = response_dict["PercentComplete"]
            time.sleep(10)
        url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
        response_dict = run_curl_command(url, "get")
        print(response_dict)
        entry_location= response_dict['Payload']['HttpHeaders'][4].split(': ')[1]
        entry_location = entry_location[2:]

        #get cper dump
        print("\n****Copying over cper.tar.xz**** \n")
        url="https://{}:8080/{}/hmc{}/attachment".format(ip , slot, entry_location)
        response = requests.get(url, auth=('root', '$pl3nd1D'), verify=False)
        if response.status_code == 200:
        # Save the response content to a file
            with open('cper.tar.xz', 'wb') as f:
                f.write(response.content)
            print("File downloaded successfully.")
        else:
            print("Failed to download the file. Status code:", response.status_code)
    
    if args.journalctl:
        # Run the journalctl task
        print("\n****Running journalctl Task**** \n")
        url="https://{}:8080/{}/hmc/redfish/v1/Systems/UBB/LogServices/DiagLogs/Actions/Oem/LogService.GetJournalControl".format(ip , slot)
        response_dict = run_curl_command(url, "post")
        print(response_dict)
        #get task id
        task_id = response_dict['@odata.id']
        task_id = task_id[2:]

        time.sleep(10)  #should wait till ask 100%

        #get task info and entry location
        print("\n****Getting journalctl Entry Location**** \n")
        url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
        response_dict = run_curl_command(url, "get")
        PercentComplete = response_dict["PercentComplete"]
        while PercentComplete != 100:
            url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
            response_dict = run_curl_command(url, "get")
            PercentComplete = response_dict["PercentComplete"]
            time.sleep(10)
        url="https://{}:8080/{}/hmc{}".format(ip , slot, task_id)
        response_dict = run_curl_command(url, "get")
        print(response_dict)
        entry_location= response_dict['Payload']['HttpHeaders'][4].split(': ')[1]
        entry_location = entry_location[2:]

        #get journalctl dump
        print("\n****Copying over journalctl.tar.xz**** \n")
        url="https://{}:8080/{}/hmc{}/attachment".format(ip , slot, entry_location)
        response = requests.get(url, auth=('root', '$pl3nd1D'), verify=False)
        if response.status_code == 200:
        # Save the response content to a file
            with open('journalctl.tar.xz', 'wb') as f:
                f.write(response.content)
            print("File downloaded successfully.")
        else:
            print("Failed to download the file. Status code:", response.status_code)
    return exit_code

      
if __name__ == "__main__":
    sys.exit(main())
