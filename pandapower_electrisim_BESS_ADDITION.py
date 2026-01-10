# Add this code to the end of pandapower_electrisim.py

class BESSControlForTargetBus(control.basic_controller.Controller):
    """
    Controller that adjusts BESS power to achieve target P and Q at Point of Coupling (POC).
    Uses iterative approach to converge to the target.
    """
    def __init__(self, net, element_index, target_p_mw, target_q_mvar, poc_bus_idx,
                 kp_p=0.5, kp_q=0.5, max_p_mw=28.0, max_q_mvar=28.0,
                 in_service=True, recycle=False, order=0, level=0, **kwargs):
        super().__init__(net, in_service=in_service, recycle=recycle, 
                        order=order, level=level, initial_run=True)
        
        self.element_index = element_index
        self.target_p_mw = target_p_mw
        self.target_q_mvar = target_q_mvar
        self.poc_bus_idx = poc_bus_idx
        self.kp_p = kp_p
        self.kp_q = kp_q
        self.max_p_mw = max_p_mw
        self.max_q_mvar = max_q_mvar
        # Start with initial guess
        # Sign convention: 
        # - If target P > 0 (consumption), BESS should DISCHARGE (negative P)
        # - If target P < 0 (generation), BESS should CHARGE (positive P)
        # Account for losses: need slightly more power than target
        initial_p = -target_p_mw * 1.05  # Negative because BESS discharges to supply load
        initial_q = -target_q_mvar * 1.05  # Negative to match sign convention
        self.p_mw = np.clip(initial_p, -max_p_mw, max_p_mw)
        self.q_mvar = np.clip(initial_q, -max_q_mvar, max_q_mvar)
        self.applied = False
        self.iteration = 0
        self.converged = False
        
    def is_converged(self, net):
        return self.applied
    
    def control_step(self, net):
        # First, set the current BESS power values
        net.storage.at[self.element_index, 'p_mw'] = self.p_mw
        net.storage.at[self.element_index, 'q_mvar'] = self.q_mvar
        
        # Run power flow to get current state (with sufficient iterations)
        try:
            pp.runpp(net, algorithm='nr', calculate_voltage_angles=True, 
                    init='auto', verbose=False)
        except Exception as e:
            # If power flow fails, don't update - keep current values
            # This can happen if the network is infeasible
            self.applied = True
            return
        
        # Get current P and Q at POC from external grid
        ext_grid_idx = net.ext_grid.index[0]
        current_p = -net.res_ext_grid.at[ext_grid_idx, 'p_mw']
        current_q = -net.res_ext_grid.at[ext_grid_idx, 'q_mvar']
        
        # Calculate error
        error_p = self.target_p_mw - current_p
        error_q = self.target_q_mvar - current_q
        
        # Check convergence
        tolerance = 1e-3
        if abs(error_p) < tolerance and abs(error_q) < tolerance:
            self.converged = True
        else:
            # Adjust BESS power proportionally to error (with damping to avoid oscillations)
            # Sign convention: 
            # - If error_p > 0 (need more consumption), decrease BESS P (more negative = more discharge)
            # - If error_p < 0 (too much consumption), increase BESS P (less negative = less discharge)
            damping = 0.5  # Damping factor to prevent oscillations
            # Error correction: if we need more P at POC, BESS should discharge more (more negative)
            delta_p = -self.kp_p * error_p * damping  # Negative because BESS P is opposite to POC P
            delta_q = -self.kp_q * error_q * damping  # Same for Q
            
            self.p_mw += delta_p
            self.q_mvar += delta_q
            
            # Apply limits
            self.p_mw = np.clip(self.p_mw, -self.max_p_mw, self.max_p_mw)
            self.q_mvar = np.clip(self.q_mvar, -self.max_q_mvar, self.max_q_mvar)
        
        self.iteration += 1
        self.applied = True


def bess_sizing(net, bess_params):
    """
    Calculate required BESS power using iterative controller approach.
    
    Uses pandapower's control framework with BESSControlForTargetBus controller
    that iteratively adjusts BESS power until target P/Q at POC is achieved.
    
    Parameters:
    -----------
    net : pandapower network
        The network object
    bess_params : dict
        Dictionary containing:
        - storageId: ID of the storage element (from frontend)
        - pocBusbarId: ID of the POC busbar (from frontend)
        - targetP: Target active power at POC (MW)
        - targetQ: Target reactive power at POC (Mvar)
        - tolerance: Convergence tolerance (default: 0.001)
        - maxIterations: Maximum control iterations (default: 50)
        - kpP: Proportional gain for active power control (default: 0.5)
        - kpQ: Proportional gain for reactive power control (default: 0.5)
        - frequency: Network frequency (default: 50)
        - algorithm: Power flow algorithm (default: 'nr')
        
    Returns:
    --------
    str : JSON string with results
    """
    try:
        # Extract parameters
        storage_id = bess_params.get('storageId')
        poc_busbar_id = bess_params.get('pocBusbarId')
        target_p = float(bess_params.get('targetP', 0.0))
        target_q = float(bess_params.get('targetQ', 0.0))
        tolerance = float(bess_params.get('tolerance', 0.001))
        max_iterations = int(bess_params.get('maxIterations', 50))
        kp_p = float(bess_params.get('kpP', 0.5))
        kp_q = float(bess_params.get('kpQ', 0.5))
        
        # Find storage element by ID (match with busbar name)
        storage_idx = None
        for idx in net.storage.index:
            # Try to match by name or bus
            storage_name = net.storage.at[idx, 'name'] if 'name' in net.storage.columns else None
            storage_bus = net.storage.at[idx, 'bus']
            
            # Match by storage ID (could be name or bus index)
            if str(storage_id) == str(storage_name) or str(storage_id) == str(storage_bus):
                storage_idx = idx
                break
        
        if storage_idx is None:
            # Fallback: use first storage element
            if len(net.storage) > 0:
                storage_idx = net.storage.index[0]
            else:
                return json.dumps({
                    'error': 'No storage element found in network',
                    'bess_p_mw': None,
                    'bess_q_mvar': None,
                    'bess_s_mva': None,
                    'achieved_p_mw': None,
                    'achieved_q_mvar': None,
                    'error_p_mw': None,
                    'error_q_mvar': None,
                    'converged': False,
                    'iterations': 0
                })
        
        # Find POC bus by ID (match with busbar name)
        poc_bus_idx = None
        for idx in net.bus.index:
            bus_name = net.bus.at[idx, 'name'] if 'name' in net.bus.columns else None
            
            # Match by POC busbar ID
            if str(poc_busbar_id) == str(bus_name) or str(poc_busbar_id) == str(idx):
                poc_bus_idx = idx
                break
        
        if poc_bus_idx is None:
            # Fallback: use first bus (usually external grid bus)
            if len(net.bus) > 0:
                poc_bus_idx = net.bus.index[0]
            else:
                return json.dumps({
                    'error': 'No POC bus found in network',
                    'bess_p_mw': None,
                    'bess_q_mvar': None,
                    'bess_s_mva': None,
                    'achieved_p_mw': None,
                    'achieved_q_mvar': None,
                    'error_p_mw': None,
                    'error_q_mvar': None,
                    'converged': False,
                    'iterations': 0
                })
        
        # Get storage bus index
        bess_bus_idx = net.storage.at[storage_idx, 'bus']
        
        # Get storage limits from network
        max_p_mw = abs(net.storage.at[storage_idx, 'sn_mva']) if 'sn_mva' in net.storage.columns else 28.0
        max_q_mvar = abs(net.storage.at[storage_idx, 'sn_mva']) if 'sn_mva' in net.storage.columns else 28.0
        
        # Create a copy of the network
        net_ctrl = deepcopy(net)
        
        # Create controller
        bess_ctrl = BESSControlForTargetBus(
            net_ctrl, storage_idx, target_p, target_q, poc_bus_idx,
            kp_p=kp_p, kp_q=kp_q, max_p_mw=max_p_mw, max_q_mvar=max_q_mvar
        )
        
        # Run iterative control loop
        for iteration in range(max_iterations):
            bess_ctrl.applied = False
            # Call control_step which will run power flow and adjust BESS power
            bess_ctrl.control_step(net_ctrl)
            if bess_ctrl.converged:
                break
        
        # Get final results
        ext_grid_idx = net_ctrl.ext_grid.index[0]
        achieved_p = -net_ctrl.res_ext_grid.at[ext_grid_idx, 'p_mw']
        achieved_q = -net_ctrl.res_ext_grid.at[ext_grid_idx, 'q_mvar']
        
        # Calculate apparent power
        bess_s_mva = np.sqrt(bess_ctrl.p_mw**2 + bess_ctrl.q_mvar**2)
        
        # Prepare response
        result = {
            'bess_p_mw': float(bess_ctrl.p_mw),
            'bess_q_mvar': float(bess_ctrl.q_mvar),
            'bess_s_mva': float(bess_s_mva),
            'achieved_p_mw': float(achieved_p),
            'achieved_q_mvar': float(achieved_q),
            'error_p_mw': float(achieved_p - target_p),
            'error_q_mvar': float(achieved_q - target_q),
            'converged': bool(bess_ctrl.converged),
            'iterations': int(bess_ctrl.iteration)
        }
        
        return json.dumps(result)
        
    except Exception as e:
        import traceback
        error_msg = f"BESS sizing calculation failed: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        
        return json.dumps({
            'error': error_msg,
            'bess_p_mw': None,
            'bess_q_mvar': None,
            'bess_s_mva': None,
            'achieved_p_mw': None,
            'achieved_q_mvar': None,
            'error_p_mw': None,
            'error_q_mvar': None,
            'converged': False,
            'iterations': 0
        })
