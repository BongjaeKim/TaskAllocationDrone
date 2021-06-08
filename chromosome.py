class Chromosome:
    def __init__(self, processing_rate_values, bandwidth_values, delay_factor_values):
        self.processing_rate_of_dec = processing_rate_values
        self.bandwidth_of_dec = bandwidth_values
        self.delay_factor_of_dec = delay_factor_values
        self.workflow_status =  [0, ]