''' 모니터링 영역 파라미터 '''
SizeOfMonitoringArea = 100

''' 에지 서버 영역 파라미터 '''
EdgeServerArea = 40

''' 클라우드 서버 영역 파라미터 '''
CloudServerArea = 60

''' 드론의 통신 반경 파라미터 '''
TransRangeOfDrone = 30

''' 네트워크 토폴리지의 드론, 에지 서버, 클라우드 서버의 수 '''
NumOfDrones = 30  # UAV의 수
NumOfEdgeServer = 4  # 에지 서버의 수
NumOfCloudServer = 2  # 클라우드 서버의 수

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
NumOfWorkflows = 5  # 워크플로우 수
MinTasksPerWorkFlow = 4  # 하나의 워크플로우의 최소 태스크 수
MaxTasksPerWorkflow = 4  # 하나의 워크플로우의 최대 태스크 수
MinRequiredProcessingPower = 50  # 각 태스크의 최소 소모 프로세싱 파워
MaxRequiredProcessingPower = 1000  # 각 태스크의 최대 소모 프로세싱 파워
MinRequiredBandwidth = 50  # 각 태스크의 최소 대역폭 파워
MaxRequiredBandwidth = 200  # 각 태스크의 최대 대역폭 파워

NodeXPositions = [0, ]  # 그래프로 각 노드 위치를 표기하기 위한 X좌표 배열
NodeYPositions = [0, ]  # 그래프로 각 노드 위치를 표기하기 위한 Y좌표 배열

MAX_MATRIX_INDEX = NumOfDrones + NumOfEdgeServer + NumOfCloudServer  # 네트워크 연결 정보 저장 테이블의 최대 인덱스

ConnectionInfo = [[0 for _ in range(MAX_MATRIX_INDEX + 1)] for __ in range(MAX_MATRIX_INDEX + 1)]  # 네트워크 연결 정보 초기화

NodePositionInfo = [(0, 0), ]  # 드론, 에지서버, 클라우드 서버의 위치 정보 저장

ProcessingRateOfDEC = [0, ]  # 각 드론, 에지서버, 클라우드 서버의 프로세싱 rate 저장

DelayFactorOfDEC = [0, ]  # 각 드론, 에지서버, 클라우드 서버의 딜레이 factor 저장

BandwidthOfDEC = [0, ]  # 각 드드 론, 에지서버, 클라우서버의 대역폭 저장

WorkflowInfo = [0, ]  # sequential 워크플로우 정보 저장