from random import *
from math import *
from parameters import *
# import copy
import matplotlib.pyplot as plt


def deploy_drone_edge_cloud(temp_position_info):  # Drone 배치하고 거리에 따라서 연결 정보 갱신
    min_value = 1
    max_value = SizeOfMonitoringArea
    for _ in range(NumOfDrones):
        pos_x = randint(min_value, max_value)
        pos_y = randint(min_value, max_value)
        NodeXPositions.append(pos_x)
        NodeYPositions.append(pos_y)
        temp_position_info.append((pos_x, pos_y))

    min_value = SizeOfMonitoringArea + 1
    max_value = SizeOfMonitoringArea + EdgeServerArea
    for _ in range(NumOfEdgeServer):
        pos_x = randint(min_value, max_value)
        pos_y = randint(1, SizeOfMonitoringArea)
        NodeXPositions.append(pos_x)
        NodeYPositions.append(pos_y)
        temp_position_info.append((pos_x, pos_y))

    min_value = SizeOfMonitoringArea + EdgeServerArea + 1
    max_value = SizeOfMonitoringArea + EdgeServerArea + CloudServerArea
    for _ in range(NumOfCloudServer):
        pos_x = randint(min_value, max_value)
        pos_y = randint(1, SizeOfMonitoringArea)
        NodeXPositions.append(pos_x)
        NodeYPositions.append(pos_y)
        temp_position_info.append((pos_x, pos_y))
    print(len(temp_position_info))
    print(temp_position_info)


def update_connection_info_d2d(temp_connection_info, temp_node_position_info):  # 네트워크 연결 정보 설정(에지 서버와 클라우드 서버)
    num_connection = 0
    for index1 in range(1, NumOfDrones):
        for index2 in range(index1 + 1, NumOfDrones + 1):
            distance_x = abs(temp_node_position_info[index1][0] - temp_node_position_info[index2][0])
            distance_y = abs(temp_node_position_info[index1][1] - temp_node_position_info[index2][1])
            if sqrt(distance_x**2 + distance_y**2) <= TransRangeOfDrone:
                # print("Can connect each other")
                num_connection += 1
                temp_connection_info[index1][index2] = 1
                temp_connection_info[index2][index1] = 1
                plt.plot([temp_node_position_info[index1][0], temp_node_position_info[index2][0]],
                         [temp_node_position_info[index1][1], temp_node_position_info[index2][1]], color="green")
    if True:  # 드론과 에지 서버와의 통신 가능 설정(4G, LTE 등과 같은 기법으로 1-Hop 통신이 가능하다고 가정)
        for index1 in range(1, NumOfDrones):
            for index2 in range(NumOfDrones + 1, NumOfDrones + NumOfEdgeServer + 1):
                temp_connection_info[index1][index2] = 1
                temp_connection_info[index2][index1] = 1
                # plt.plot([temp_node_position_info[index1][0], temp_node_position_info[index2][0]],
                #          [temp_node_position_info[index1][1], temp_node_position_info[index2][1]], color="black")
    print("[DBG]", "The Number of Total Connection", num_connection)


def update_connection_info_e2c(temp_connection_info, temp_node_position_info):  # 네트워크 연결 정보 설정(에지 서버와 클라우드 서버)
    for index1 in range(NumOfDrones + 1, NumOfDrones + NumOfEdgeServer + 1):
        for index2 in range(NumOfDrones + NumOfEdgeServer + 1, MAX_MATRIX_INDEX + 1):
            temp_connection_info[index1][index2] = 1
            temp_connection_info[index2][index1] = 1
            plt.plot([temp_node_position_info[index1][0], temp_node_position_info[index2][0]],
                     [temp_node_position_info[index1][1], temp_node_position_info[index2][1]], color="black")


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


def alloc_bandwidth(temp_alloc_bandwidth_of_dec):
    for _ in range(0, NumOfDrones):
        temp_alloc_bandwidth_of_dec.append(BandwidthOfDrone)
    for _ in range(0, NumOfEdgeServer):
        temp_alloc_bandwidth_of_dec.append(BandwidthOfEdgeServer)
    for _ in range(0, NumOfCloudServer):
        temp_alloc_bandwidth_of_dec.append(BandwidthOfCloudServer)


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
        print("[DBG]", "No of Tasks:", cur_task, ", Found allocatable case:", visited_node)
        return True

    for index in range(1, MAX_MATRIX_INDEX + 1):
        if index != cur_node:
            if cur_connection_info[cur_node][index] != 0 and index not in visited_node:
                visited_node.append(index)
                ret = allocate_workflows_to_topology(cur_connection_info, workflow, start_node,
                                                     index, cur_task + 1, visited_node)
                if ret is True:
                    return True


def set_resource_usage_on_topology(temp_visited_node_info, temp_workflow):
    for index in range(len(temp_visited_node_info)):
        ProcessingRateOfDEC[temp_visited_node_info[index]] -= temp_workflow[index][1]
        BandwidthOfDEC[temp_visited_node_info[index]] -= temp_workflow[index][2]

def allocate_workflows_to_topology_with_constraint(cur_connection_info, workflow, start_node,
                                                   cur_node, cur_task, visited_node):
    if cur_task == len(workflow):
        # check remained resources at current checking node
        # a workflow is consist of ( task number, required_processing_power, required_bandwidth )
        # print("[DBG]", "current node is", cur_node)
        if ProcessingRateOfDEC[cur_node] > workflow[cur_task - 1][1] and \
                BandwidthOfDEC[cur_node] > workflow[cur_task - 1][2]:
            print("[DBG]", "No of Tasks:", cur_task, ", Found allocatable case:", visited_node)
            return True
        else:
            return False

    for next_node in range(1, MAX_MATRIX_INDEX + 1):
        if next_node != cur_node:
            if cur_connection_info[cur_node][next_node] != 0 and \
                    next_node not in visited_node:
                # check remained resources at current checking node
                # a workflow is consist of ( task number, required_processing_power, required_bandwidth )
                if ProcessingRateOfDEC[cur_node] > workflow[cur_task - 1][1] and \
                        BandwidthOfDEC[cur_node] > workflow[cur_task - 1][2]:
                    visited_node.append(next_node)
                    ret = allocate_workflows_to_topology_with_constraint(cur_connection_info, workflow, start_node,
                                                                         next_node, cur_task + 1, visited_node)
                    if ret is True:
                        return True
                    else:
                        return False
                else:
                    return False

def display_deployed_workflow(temp_deployed_status_of_workflows):
    for index in range(1, len(temp_deployed_status_of_workflows)):
        if temp_deployed_status_of_workflows[index][0] is True:
            print("[DBG]", temp_deployed_status_of_workflows[index][1])


def add_candidate_deployment(temp_node_position_info, temp_visited_node_info):  # 워크플로우 할당 현황 표시
    r = random()
    b = random()
    g = random()
    generated_color = (r, g, b)
    num_of_total_visited_node = len(temp_visited_node_info)
    for index1 in range(num_of_total_visited_node - 1):
        start_node_index = temp_visited_node_info[index1]
        end_node_index = temp_visited_node_info[index1 + 1]
        plt.plot([temp_node_position_info[start_node_index][0], temp_node_position_info[end_node_index][0]],
                 [temp_node_position_info[start_node_index][1], temp_node_position_info[end_node_index][1]],
                 color=generated_color)


deploy_drone_edge_cloud(NodePositionInfo)  # 드론(UAV), 에지, 클라우드를 모니터링 대상 영역에 배치

update_connection_info_e2c(ConnectionInfo, NodePositionInfo)  # 에지 서버와 클라우드 서버간의 연결 정보 생성

update_connection_info_d2d(ConnectionInfo, NodePositionInfo)  # 드론간의 토폴로지 생성

alloc_processing_power(ProcessingRateOfDEC)  # 드론, 에지 서버, 클라우드 서버의 프로세싱 rate 초기화

alloc_delay_factor(DelayFactorOfDEC)  # 드론, 에지 서버, 클라우드 서버의 딜레이 factor 초기화

alloc_bandwidth(BandwidthOfDEC)  # 드론, 에지 서버, 클라우드 서버의 bandwidth 초기화

display_connection_info(ConnectionInfo)  # 전체 토폴로지 연결 정보 표시

make_workflows(WorkflowInfo)  # workflow 를 생성

# 램덤 방식일 이용하여 각 워크플로우를 할당
SuccessNumber = 0
for i in range(1, NumOfWorkflows + 1):
    Rnd_Start_Node = randint(1, MAX_MATRIX_INDEX)
    Visited_Node_Info = [Rnd_Start_Node]
    print("[DBG]", "Initial starting node info.:", Visited_Node_Info)
    Condition = False

    ret_value = allocate_workflows_to_topology_with_constraint(ConnectionInfo, WorkflowInfo[i],
                                                               start_node=Rnd_Start_Node, cur_node=Rnd_Start_Node,
                                                               cur_task=1,
                                                               visited_node=Visited_Node_Info)

    '''
    ret_value = allocate_workflows_to_topology(ConnectionInfo, WorkflowInfo[i],
                                               start_node=Rnd_Start_Node, cur_node=Rnd_Start_Node, cur_task=1,
                                               visited_node=Visited_Node_Info)
    '''
    print(Visited_Node_Info)  # 워크플로우가 배치된 노트 정보 출력
    
    if ret_value is True:
        DeployedStatusOfWorkflows.append((True, Visited_Node_Info))
        SuccessNumber += 1
        set_resource_usage_on_topology(Visited_Node_Info, WorkflowInfo[i])  # 실제 토폴로지에서 리소스 사용을 반영시킴
        add_candidate_deployment(NodePositionInfo, Visited_Node_Info)  # 가시화를 위한 워크플로우의 배치 정보 추가
    else:
        DeployedStatusOfWorkflows.append((False, [0,]))
        print("[DBG]", "current workflow is not allocated")

print("[DBG]", "# of allocated workflow = ", SuccessNumber)

display_deployed_workflow(DeployedStatusOfWorkflows)

'''
print(WorkflowInfo)
print(len(WorkflowInfo))
'''

# print(DelayFactorOfDEC)
# print(len(DelayFactorOfDEC))

''' deep copy sample code 
test = copy.deepcopy(DelayFactorOfDEC)
'''

# 드론들의 배치 상황과 연결 상황을 그래프로 표시
plt.scatter(NodeXPositions[1:NumOfDrones + 1], NodeYPositions[1:NumOfDrones + 1], edgecolors="blue", s=30)
plt.scatter(NodeXPositions[NumOfDrones + 1:NumOfDrones + NumOfEdgeServer + 1],
            NodeYPositions[NumOfDrones + 1:NumOfDrones + NumOfEdgeServer + 1], edgecolors="black", s=80)
plt.scatter(NodeXPositions[NumOfDrones + NumOfEdgeServer + 1:],
            NodeYPositions[NumOfDrones + NumOfEdgeServer + 1:], edgecolors="red", s=150)
plt.fill_between([1, SizeOfMonitoringArea],
                 [SizeOfMonitoringArea, SizeOfMonitoringArea], alpha=0.1)
plt.fill_between([SizeOfMonitoringArea, SizeOfMonitoringArea + EdgeServerArea],
                 [SizeOfMonitoringArea, SizeOfMonitoringArea], alpha=0.2)
plt.fill_between([SizeOfMonitoringArea + EdgeServerArea, SizeOfMonitoringArea + EdgeServerArea + CloudServerArea],
                 [SizeOfMonitoringArea, SizeOfMonitoringArea], alpha=0.1)
plt.show()
