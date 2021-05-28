from random import *
from math import *
# import copy
import matplotlib.pyplot as plt

''' 모니터링 영역 파라미터 '''
SizeOfMonitoringArea = 100

''' 드론의 통신 반경 파라미터 '''
TransRangeOfDrone = 30

''' 네트워크 토폴리지의 드론, 에지 서버, 클라우드 서버의 수 '''
NumOfDrones = 30  # UAV의 수
NumOfEdgeServer = 2  # 에지 서버의 수
NumOfCloudServer = 1  # 클라우드 서버의 수

''' 프로세싱 Rate 파라미터 '''
MaxProcessingRateOfDrone = 100
MaxProcessingRateOfEdgeServer = 500
MaxProcessingRateOfCloudServer = 10000

''' 딜레이 Factor 파라미터 '''
MaxDelayFactorOfDrone = 1  # 드론의 딜레이 factor
MaxDelayFactorOfEdgeServer = 5  # 에지 서버의 딜레이 factor
MaxDelayFactorOfCloudServer = 6   # 클라우드 서버의 딜레이 factor

''' 대역폭 파라미터 '''
BandwidthOfDrone = 200  # 드론의 딜레이 factor
BandwidthOfEdgeServer = 400  # 에지 서버의 딜레이 factor
BandwidthOfCloudServer = 1000  # 클라우드 서버의 딜레이 factor

''' 워크플로우 관련 파라미터 '''
NumOfWorkflows = 1
MinTasksPerWorkFlow = 5
MaxTasksPerWorkflow = 10
MinRequiredProcessingPower = 50
MaxRequiredProcessingPower = 1000
MinRequiredBandwidth = 50
MaxRequiredBandwidth = 200

DronesXPositions = []  # 그래프로 드론의 위치를 표기하기 위한 드론의 X좌표 배열
DronesYPositions = []  # 그래프로 드론의 위치를 표기하기 위한 드론의 Y좌표 배열

MAX_MATRIX_INDEX = NumOfDrones + NumOfEdgeServer + NumOfCloudServer  # 네트워크 연결 정보 저장 테이블의 최대 인덱스

ConnectionInfo = [[0 for _ in range(MAX_MATRIX_INDEX + 1)] for __ in range(MAX_MATRIX_INDEX + 1)]  # 네트워크 연결 정보 초기화

DronesPositionInfo = [(0, 0), ]  # 드론들의 위치 정보 저장

ProcessingRateOfDEC = [0, ]  # 각 드론, 에지서버, 클라우드 서버의 프로세싱 rate 저장

DelayFactorOfDEC = [0, ]  # 각 드론, 에지서버, 클라우드 서버의 딜레이 factor 저장

BandwidthOfDEC = [0, ]  # 각 드드 론, 에지서버, 클라우서버의 대역폭 저장

WorkflowInfo = [0, ]  # sequential 워크플로우 정보 저장


def deploy_drone(temp_drones_position_info):  # Drone 배치하고 거리에 따라서 연결 정보 갱신
    for i in range(NumOfDrones):
        pos_x = randint(1, SizeOfMonitoringArea)
        pos_y = randint(1, SizeOfMonitoringArea)
        DronesXPositions.append(pos_x)
        DronesYPositions.append(pos_y)
        temp_drones_position_info.append((pos_x, pos_y))
    print(len(temp_drones_position_info))
    print(temp_drones_position_info)


def update_connection_info_d2d(temp_connection_info, temp_drones_position_info):  # 네트워크 연결 정보 설정(에지 서버와 클라우드 서버)
    num_connection = 0
    for index1 in range(1, NumOfDrones):
        for index2 in range(index1 + 1, NumOfDrones + 1):
            distance_x = abs(temp_drones_position_info[index1][0] - temp_drones_position_info[index2][0])
            distance_y = abs(temp_drones_position_info[index1][1] - temp_drones_position_info[index2][1])
            if sqrt(distance_x**2 + distance_y**2) <= TransRangeOfDrone:
                # print("Can connect each other")
                num_connection += 1
                temp_connection_info[index1][index2] = 1
                temp_connection_info[index2][index1] = 1
                plt.plot([temp_drones_position_info[index1][0], temp_drones_position_info[index2][0]],
                         [temp_drones_position_info[index1][1], temp_drones_position_info[index2][1]], color="green")
    print("The Number of Total Connection", num_connection)


def update_connection_info_e2c(temp_connection_info):  # 네트워크 연결 정보 설정(에지 서버와 클라우드 서버)
    for index1 in range(NumOfDrones + 1, NumOfDrones + NumOfEdgeServer + 1):
        for index2 in range(NumOfDrones + NumOfEdgeServer + 1, MAX_MATRIX_INDEX + 1):
            temp_connection_info[index1][index2] = 1
            temp_connection_info[index2][index1] = 1


def display_connection_info(temp_connection_info):  # 현재 내트워크 연결 정보 출력
    for index1 in range(1, MAX_MATRIX_INDEX + 1):
        for index2 in range(1, MAX_MATRIX_INDEX + 1):
            print(temp_connection_info[index1][index2], end=' ')
        print()


def alloc_processing_power(temp_processing_rate_of_dec):
    for _ in range(0, NumOfDrones):
        temp_processing_rate_of_dec.append(MaxProcessingRateOfDrone)
    for _ in range(0, NumOfEdgeServer):
        temp_processing_rate_of_dec.append(MaxProcessingRateOfEdgeServer)
    for _ in range(0, NumOfCloudServer):
        temp_processing_rate_of_dec.append(MaxProcessingRateOfCloudServer)


def alloc_delay_factor(temp_delay_factor_of_dec):
    for _ in range(0, NumOfDrones):
        temp_delay_factor_of_dec.append(MaxDelayFactorOfDrone)
    for _ in range(0, NumOfEdgeServer):
        temp_delay_factor_of_dec.append(MaxDelayFactorOfEdgeServer)
    for _ in range(0, NumOfCloudServer):
        temp_delay_factor_of_dec.append(MaxDelayFactorOfCloudServer)


def make_workflows(temp_workflow_info):
    for index in range(NumOfWorkflows):
        num_of_task = randint(MinTasksPerWorkFlow, MaxTasksPerWorkflow)
        temp_task = []
        for index2 in range(1, num_of_task + 1):
            required_processing_power = randint(MinRequiredProcessingPower, MaxRequiredProcessingPower)
            required_bandwidth = randint(MinRequiredBandwidth, MaxRequiredBandwidth)
            temp_task.append((index2, required_processing_power, required_bandwidth))
        temp_workflow_info.append(temp_task)


def allocate_workflows_to_topology(cur_connection_info, workflow, start_node, cur_node, cur_task, visited_node):
    if cur_task == len(workflow):
        print("[DBG]", "No of Tasks: ", cur_task, ", Found allocatable case: ", visited_node)
        return True

    for index in range(1, MAX_MATRIX_INDEX + 1):
        if index != cur_node:
            if cur_connection_info[cur_node][index] != 0 and index not in visited_node:
                if start_node == cur_node:
                    visited_node.append(cur_node)
                visited_node.append(index)
                ret_value = allocate_workflows_to_topology(cur_connection_info, workflow, start_node, index, cur_task + 1, visited_node)
                if ret_value is True:
                    return True


def add_candidate_deployment(temp_drones_position_info, temp_visited_node_info):  # 네트워크 연결 정보 설정(에지 서버와 클라우드 서버)
    for index1 in range(len(temp_visited_node_info)-1):
        plt.plot([temp_drones_position_info[temp_visited_node_info[index1]][0], temp_drones_position_info[temp_visited_node_info[index1+1]][0]],
                 [temp_drones_position_info[temp_visited_node_info[index1]][1], temp_drones_position_info[temp_visited_node_info[index1+1]][1]], color="black")


update_connection_info_e2c(ConnectionInfo)  # 에지 서버와 클라우드 서버간의 연결 정보 생성
deploy_drone(DronesPositionInfo)  # 드론(UAV)를 모니터링 대상 영역에 배치
update_connection_info_d2d(ConnectionInfo, DronesPositionInfo)  # 드론간의 토폴로지 생성
alloc_processing_power(ProcessingRateOfDEC)  # 드론, 에지 서버, 클라우드 서버의 프로세싱 rate 초기화
alloc_delay_factor(DelayFactorOfDEC)  # 드론, 에지 서버, 클라우드 서버의 프로세싱 rate 초기화
display_connection_info(ConnectionInfo)  # 전체 토폴로지 연결 정보 표시
make_workflows(WorkflowInfo)  # workflow를 생성


Rnd_Start_Node = randint(1, MAX_MATRIX_INDEX)
Visited_Node_Info = []
Condition = False
allocate_workflows_to_topology(ConnectionInfo, WorkflowInfo[1], start_node=Rnd_Start_Node, cur_node=Rnd_Start_Node, cur_task=1, visited_node=Visited_Node_Info)
print(Visited_Node_Info)

add_candidate_deployment(DronesPositionInfo, Visited_Node_Info)

print(WorkflowInfo)
print(len(WorkflowInfo))
#
# print(DelayFactorOfDEC)
# print(len(DelayFactorOfDEC))

''' deep copy sample code 
test = copy.deepcopy(DelayFactorOfDEC)
'''

# 드론들의 배치 상황과 연결 상황을 그래프로 표시
plt.scatter(DronesXPositions, DronesYPositions)
plt.show()
