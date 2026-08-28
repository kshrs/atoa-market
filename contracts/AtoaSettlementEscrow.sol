// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AtoaSettlementEscrow
 * @author Ashwin Balaji G
 * @notice Decentralized smart escrow and bonding settlement protocol for autonomous Agent-to-Agent (A2A) economies.
 * @dev Manages zero-trust escrow deposits, worker collateral bonding, oracle-based verification settlement,
 *      and game-theoretic slashing mechanisms with reentrancy protection and role-based access control.
 */

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}

library SafeERC20 {
    function safeTransfer(IERC20 token, address to, uint256 value) internal {
        _callOptionalReturn(token, abi.encodeWithSelector(token.transfer.selector, to, value));
    }

    function safeTransferFrom(IERC20 token, address from, address to, uint256 value) internal {
        _callOptionalReturn(token, abi.encodeWithSelector(token.transferFrom.selector, from, to, value));
    }

    function _callOptionalReturn(IERC20 token, bytes memory data) private {
        require(address(token).code.length > 0, "SafeERC20: call to non-contract");
        (bool success, bytes memory returndata) = address(token).call(data);
        require(success, "SafeERC20: low-level call failed");

        if (returndata.length > 0) {
            require(abi.decode(returndata, (bool)), "SafeERC20: ERC20 operation did not succeed");
        }
    }
}

contract AtoaSettlementEscrow {
    using SafeERC20 for IERC20;

    // --- ENUMS & STRUCTS ---

    enum TaskState {
        None,        // 0: Uninitialized
        Deposited,   // 1: Escrow deposited by Requester, awaiting Worker bond
        Active,      // 2: Worker bond locked, task in progress
        Settled,     // 3: Successfully verified and paid out to Worker
        Slashed,     // 4: Verification failed; Worker bond slashed & Escrow refunded
        Cancelled    // 5: Cancelled by Requester before Worker joined, Escrow refunded
    }

    struct TaskEscrow {
        bytes32 taskId;
        address requester;
        address worker;
        uint256 escrowAmount;
        uint256 workerBond;
        TaskState state;
        uint256 createdAt;
        uint256 settledAt;
    }

    // --- STATE VARIABLES ---

    /// @notice The ERC20 settlement token (e.g., USDC)
    IERC20 public immutable settlementToken;

    /// @notice Protocol Owner with administrative powers
    address public protocolOwner;

    /// @notice Authorized Oracle / Backend Relayer that submits verification results
    address public protocolOracle;

    /// @notice Protocol treasury / fee collector address
    address public feeRecipient;

    /// @notice Basis points for protocol fee on slashing/settlement (e.g., 200 = 2%)
    uint256 public protocolFeeBps = 0;

    /// @notice Task storage mapping: taskId (keccak256 hash) => TaskEscrow
    mapping(bytes32 => TaskEscrow) public tasks;

    /// @notice Track registered task IDs
    bytes32[] public taskRegistry;

    // --- REENTRANCY GUARD ---
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _reentrancyStatus;

    // --- PAUSE CONTROL ---
    bool public paused;

    // --- EVENTS ---

    event EscrowDeposited(
        bytes32 indexed taskId,
        address indexed requester,
        uint256 amount,
        uint256 timestamp
    );

    event WorkerBondLocked(
        bytes32 indexed taskId,
        address indexed worker,
        uint256 bondAmount,
        uint256 timestamp
    );

    event TaskSettled(
        bytes32 indexed taskId,
        address indexed worker,
        uint256 payoutAmount,
        uint256 bondReturned,
        uint256 timestamp
    );

    event WorkerSlashed(
        bytes32 indexed taskId,
        address indexed worker,
        address indexed requester,
        uint256 slashedBond,
        uint256 escrowRefunded,
        uint256 timestamp
    );

    event TaskCancelled(
        bytes32 indexed taskId,
        address indexed requester,
        uint256 amountRefunded,
        uint256 timestamp
    );

    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    event FeeRecipientUpdated(address indexed oldRecipient, address indexed newRecipient);
    event ProtocolFeeBpsUpdated(uint256 oldFeeBps, uint256 newFeeBps);
    event OwnershipTransferred(address indexed oldOwner, address indexed newOwner);
    event PauseToggled(bool isPaused);

    // --- CUSTOM ERRORS ---

    error ZeroAddress();
    error ZeroAmount();
    error ZeroTaskId();
    error TaskAlreadyExists(bytes32 taskId);
    error TaskNotFound(bytes32 taskId);
    error InvalidTaskState(bytes32 taskId, TaskState current, TaskState expected);
    error UnauthorizedCaller(address caller);
    error InvalidWorkerAddress(address expected, address actual);
    error InvalidRequesterAddress(address expected, address actual);
    error ContractIsPaused();
    error ReentrantCall();

    // --- MODIFIERS ---

    modifier onlyOwner() {
        if (msg.sender != protocolOwner) revert UnauthorizedCaller(msg.sender);
        _;
    }

    modifier onlyProtocolOrOwner() {
        if (msg.sender != protocolOracle && msg.sender != protocolOwner) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    modifier nonReentrant() {
        if (_reentrancyStatus == _ENTERED) revert ReentrantCall();
        _reentrancyStatus = _ENTERED;
        _;
        _reentrancyStatus = _NOT_ENTERED;
    }

    modifier whenNotPaused() {
        if (paused) revert ContractIsPaused();
        _;
    }

    // --- CONSTRUCTOR ---

    /**
     * @notice Initializes the AtoaSettlementEscrow contract.
     * @param _settlementToken Address of the ERC20 token used for settlements (e.g., USDC).
     * @param _protocolOracle Address of the backend oracle service authorized to trigger settlements/slashes.
     * @param _feeRecipient Address that receives protocol fees if configured.
     */
    constructor(
        address _settlementToken,
        address _protocolOracle,
        address _feeRecipient
    ) {
        if (_settlementToken == address(0) || _protocolOracle == address(0) || _feeRecipient == address(0)) {
            revert ZeroAddress();
        }

        settlementToken = IERC20(_settlementToken);
        protocolOwner = msg.sender;
        protocolOracle = _protocolOracle;
        feeRecipient = _feeRecipient;
        _reentrancyStatus = _NOT_ENTERED;
    }

    // --- CORE ESCROW & BONDING FUNCTIONS ---

    /**
     * @notice Locks USDC escrow into the contract for a specific task.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param amount The amount of settlement tokens to lock into escrow.
     */
    function depositEscrow(
        bytes32 taskId,
        uint256 amount
    ) external nonReentrant whenNotPaused {
        _depositEscrowInternal(taskId, msg.sender, amount);
    }

    /**
     * @notice Relayed/Explicit deposit function allowing the backend protocol to deposit on behalf of a requester.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param requester The address of the task creator/requester.
     * @param amount The amount of settlement tokens to deposit.
     */
    function depositEscrowFor(
        bytes32 taskId,
        address requester,
        uint256 amount
    ) external nonReentrant whenNotPaused {
        if (requester == address(0)) revert ZeroAddress();
        address payer = (msg.sender == protocolOracle || msg.sender == protocolOwner) ? msg.sender : requester;
        _depositEscrowInternal(taskId, requester, amount, payer);
    }

    /**
     * @notice Overload for direct taskId deposit (uses full transfer allowance).
     * @param taskId Keccak256 hash of the task_id.
     */
    function depositEscrow(bytes32 taskId) external nonReentrant whenNotPaused {
        uint256 allowed = settlementToken.allowance(msg.sender, address(this));
        if (allowed == 0) revert ZeroAmount();
        _depositEscrowInternal(taskId, msg.sender, allowed);
    }

    /**
     * @notice Allows a Worker agent to lock their collateral bond for a specific task.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param bondAmount The collateral bond amount to lock.
     */
    function lockWorkerBond(
        bytes32 taskId,
        uint256 bondAmount
    ) external nonReentrant whenNotPaused {
        _lockWorkerBondInternal(taskId, msg.sender, bondAmount);
    }

    /**
     * @notice Relayed/Explicit bond lock function allowing the backend protocol to lock bond on behalf of a worker.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param worker The address of the worker agent.
     * @param bondAmount The collateral bond amount to lock.
     */
    function lockWorkerBondFor(
        bytes32 taskId,
        address worker,
        uint256 bondAmount
    ) external nonReentrant whenNotPaused {
        if (worker == address(0)) revert ZeroAddress();
        address payer = (msg.sender == protocolOracle || msg.sender == protocolOwner) ? msg.sender : worker;
        _lockWorkerBondInternal(taskId, worker, bondAmount, payer);
    }

    /**
     * @notice Overload for direct worker bond locking based on allowance.
     * @param taskId Keccak256 hash of the task_id.
     */
    function lockWorkerBond(bytes32 taskId) external nonReentrant whenNotPaused {
        uint256 allowed = settlementToken.allowance(msg.sender, address(this));
        if (allowed == 0) revert ZeroAmount();
        _lockWorkerBondInternal(taskId, msg.sender, allowed);
    }

    /**
     * @notice Called by authorized protocol oracle to release escrow + return collateral bond to the worker.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param worker Address of the worker receiving payout and bond refund.
     */
    function settlePayout(
        bytes32 taskId,
        address worker
    ) external onlyProtocolOrOwner nonReentrant whenNotPaused {
        TaskEscrow storage task = tasks[taskId];

        if (task.state == TaskState.None) revert TaskNotFound(taskId);
        if (task.state != TaskState.Active && task.state != TaskState.Deposited) {
            revert InvalidTaskState(taskId, task.state, TaskState.Active);
        }
        if (worker == address(0)) revert ZeroAddress();

        if (task.worker == address(0)) {
            task.worker = worker;
        } else if (task.worker != worker) {
            revert InvalidWorkerAddress(task.worker, worker);
        }

        uint256 escrowToPay = task.escrowAmount;
        uint256 bondToReturn = task.workerBond;
        uint256 totalPayout = escrowToPay + bondToReturn;

        task.state = TaskState.Settled;
        task.settledAt = block.timestamp;

        settlementToken.safeTransfer(worker, totalPayout);

        emit TaskSettled(taskId, worker, escrowToPay, bondToReturn, block.timestamp);
    }

    /**
     * @notice Called by protocol oracle upon failed verification to slash the worker bond and refund the requester.
     * @param taskId Keccak256 hash of the unique string task_id.
     * @param worker Address of the worker agent whose bond is slashed.
     * @param requester Address of the requester receiving the escrow refund + slashed bond compensation.
     */
    function slashWorker(
        bytes32 taskId,
        address worker,
        address requester
    ) external onlyProtocolOrOwner nonReentrant whenNotPaused {
        TaskEscrow storage task = tasks[taskId];

        if (task.state == TaskState.None) revert TaskNotFound(taskId);
        if (task.state != TaskState.Active && task.state != TaskState.Deposited) {
            revert InvalidTaskState(taskId, task.state, TaskState.Active);
        }
        if (worker == address(0) || requester == address(0)) revert ZeroAddress();

        if (task.requester != address(0) && task.requester != requester) {
            revert InvalidRequesterAddress(task.requester, requester);
        }

        if (task.worker != address(0) && task.worker != worker) {
            revert InvalidWorkerAddress(task.worker, worker);
        }

        uint256 escrowToRefund = task.escrowAmount;
        uint256 bondToSlash = task.workerBond;

        task.state = TaskState.Slashed;
        task.settledAt = block.timestamp;

        // Refund escrow to requester
        if (escrowToRefund > 0) {
            settlementToken.safeTransfer(requester, escrowToRefund);
        }

        // Transfer slashed bond
        if (bondToSlash > 0) {
            if (protocolFeeBps > 0 && feeRecipient != address(0)) {
                uint256 fee = (bondToSlash * protocolFeeBps) / 10000;
                uint256 compensation = bondToSlash - fee;

                if (fee > 0) {
                    settlementToken.safeTransfer(feeRecipient, fee);
                }
                if (compensation > 0) {
                    settlementToken.safeTransfer(requester, compensation);
                }
            } else {
                settlementToken.safeTransfer(requester, bondToSlash);
            }
        }

        emit WorkerSlashed(taskId, worker, requester, bondToSlash, escrowToRefund, block.timestamp);
    }

    /**
     * @notice Allows a requester or protocol to cancel an unassigned task and recover the escrow.
     * @param taskId Keccak256 hash of the unique string task_id.
     */
    function cancelTask(bytes32 taskId) external nonReentrant whenNotPaused {
        TaskEscrow storage task = tasks[taskId];

        if (task.state == TaskState.None) revert TaskNotFound(taskId);
        if (task.state != TaskState.Deposited) {
            revert InvalidTaskState(taskId, task.state, TaskState.Deposited);
        }

        if (msg.sender != task.requester && msg.sender != protocolOwner && msg.sender != protocolOracle) {
            revert UnauthorizedCaller(msg.sender);
        }

        uint256 refundAmount = task.escrowAmount;
        address requester = task.requester;

        task.state = TaskState.Cancelled;
        task.settledAt = block.timestamp;

        if (refundAmount > 0) {
            settlementToken.safeTransfer(requester, refundAmount);
        }

        emit TaskCancelled(taskId, requester, refundAmount, block.timestamp);
    }

    // --- INTERNAL HELPERS ---

    function _depositEscrowInternal(bytes32 taskId, address requester, uint256 amount) internal {
        _depositEscrowInternal(taskId, requester, amount, requester);
    }

    function _depositEscrowInternal(
        bytes32 taskId,
        address requester,
        uint256 amount,
        address tokenSource
    ) internal {
        if (taskId == bytes32(0)) revert ZeroTaskId();
        if (amount == 0) revert ZeroAmount();
        if (requester == address(0)) revert ZeroAddress();

        TaskEscrow storage task = tasks[taskId];
        if (task.state != TaskState.None) revert TaskAlreadyExists(taskId);

        task.taskId = taskId;
        task.requester = requester;
        task.escrowAmount = amount;
        task.state = TaskState.Deposited;
        task.createdAt = block.timestamp;

        taskRegistry.push(taskId);

        settlementToken.safeTransferFrom(tokenSource, address(this), amount);

        emit EscrowDeposited(taskId, requester, amount, block.timestamp);
    }

    function _lockWorkerBondInternal(bytes32 taskId, address worker, uint256 bondAmount) internal {
        _lockWorkerBondInternal(taskId, worker, bondAmount, worker);
    }

    function _lockWorkerBondInternal(
        bytes32 taskId,
        address worker,
        uint256 bondAmount,
        address tokenSource
    ) internal {
        if (taskId == bytes32(0)) revert ZeroTaskId();
        if (worker == address(0)) revert ZeroAddress();

        TaskEscrow storage task = tasks[taskId];
        if (task.state == TaskState.None) revert TaskNotFound(taskId);
        if (task.state != TaskState.Deposited) {
            revert InvalidTaskState(taskId, task.state, TaskState.Deposited);
        }

        task.worker = worker;
        task.workerBond = bondAmount;
        task.state = TaskState.Active;

        if (bondAmount > 0) {
            settlementToken.safeTransferFrom(tokenSource, address(this), bondAmount);
        }

        emit WorkerBondLocked(taskId, worker, bondAmount, block.timestamp);
    }

    // --- VIEW FUNCTIONS ---

    function getTask(bytes32 taskId) external view returns (TaskEscrow memory) {
        return tasks[taskId];
    }

    function getTaskState(bytes32 taskId) external view returns (TaskState) {
        return tasks[taskId].state;
    }

    function getTotalTasks() external view returns (uint256) {
        return taskRegistry.length;
    }

    // --- ADMIN CONFIGURATION ---

    function setProtocolOracle(address _newOracle) external onlyOwner {
        if (_newOracle == address(0)) revert ZeroAddress();
        emit OracleUpdated(protocolOracle, _newOracle);
        protocolOracle = _newOracle;
    }

    function setFeeRecipient(address _newFeeRecipient) external onlyOwner {
        if (_newFeeRecipient == address(0)) revert ZeroAddress();
        emit FeeRecipientUpdated(feeRecipient, _newFeeRecipient);
        feeRecipient = _newFeeRecipient;
    }

    function setProtocolFeeBps(uint256 _newFeeBps) external onlyOwner {
        require(_newFeeBps <= 2000, "Fee cannot exceed 20%");
        emit ProtocolFeeBpsUpdated(protocolFeeBps, _newFeeBps);
        protocolFeeBps = _newFeeBps;
    }

    function transferOwnership(address _newOwner) external onlyOwner {
        if (_newOwner == address(0)) revert ZeroAddress();
        emit OwnershipTransferred(protocolOwner, _newOwner);
        protocolOwner = _newOwner;
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PauseToggled(_paused);
    }
}
