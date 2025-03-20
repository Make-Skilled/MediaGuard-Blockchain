// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./MediaGuardToken.sol";

contract MediaGuard is Ownable {
    MediaGuardToken public token;
    uint256 public rewardAmount = 10 * 10**18; // 10 tokens
    uint256 public reportThreshold = 3;
    mapping(address => uint256) public reportCount;
    mapping(address => bool) public isBlocked;
    mapping(address => bool) public hasReported;
    mapping(address => uint256) public lastReportTime;
    uint256 public cooldownPeriod = 1 days;
    mapping(address => bool) public hasUnblockRequest;
    mapping(address => uint256) public unblockRequestDate;

    // Post-related state variables
    struct Post {
        address author;
        string contentHash;
        uint256 vulgarityScore;
        bool isBlocked;
        uint256 createdAt;
    }
    Post[] public posts;
    mapping(uint256 => bool) public isPostBlocked;

    event ContentReported(address indexed reporter, address indexed reported);
    event UserBlocked(address indexed user);
    event UserUnblocked(address indexed user);
    event RewardPaid(address indexed user, uint256 amount);
    event PostCreated(address indexed author, uint256 indexed postId, string contentHash, uint256 vulgarityScore);
    event PostBlocked(uint256 indexed postId);
    event UnblockRequested(address indexed user);

    constructor(address _tokenAddress) {
        token = MediaGuardToken(_tokenAddress);
    }

    function createPost(string memory _contentHash, uint256 _vulgarityScore) external {
        require(!isBlocked[msg.sender], "User is blocked");
        require(_vulgarityScore <= 100, "Invalid vulgarity score");

        uint256 postId = posts.length;
        posts.push(Post({
            author: msg.sender,
            contentHash: _contentHash,
            vulgarityScore: _vulgarityScore,
            isBlocked: false,
            createdAt: block.timestamp
        }));

        emit PostCreated(msg.sender, postId, _contentHash, _vulgarityScore);

        // Block post if vulgarity score is too high
        if (_vulgarityScore >= 60) {
            isPostBlocked[postId] = true;
            emit PostBlocked(postId);
        }
    }

    function getPost(uint256 _postId) external view returns (
        address author,
        string memory contentHash,
        uint256 vulgarityScore,
        bool isBlocked,
        uint256 createdAt
    ) {
        require(_postId < posts.length, "Post does not exist");
        Post memory post = posts[_postId];
        return (
            post.author,
            post.contentHash,
            post.vulgarityScore,
            post.isBlocked,
            post.createdAt
        );
    }

    function getPostCount() external view returns (uint256) {
        return posts.length;
    }

    function requestUnblock() external {
        require(isBlocked[msg.sender], "User is not blocked");
        require(!hasUnblockRequest[msg.sender], "User already has a pending unblock request");
        
        hasUnblockRequest[msg.sender] = true;
        unblockRequestDate[msg.sender] = block.timestamp;
        
        emit UnblockRequested(msg.sender);
    }

    function reportContent(address reportedUser) external {
        require(!isBlocked[reportedUser], "User is already blocked");
        require(!hasReported[msg.sender] || block.timestamp >= lastReportTime[msg.sender] + cooldownPeriod, "Cooldown period not over");
        
        reportCount[reportedUser]++;
        hasReported[msg.sender] = true;
        lastReportTime[msg.sender] = block.timestamp;

        emit ContentReported(msg.sender, reportedUser);

        if (reportCount[reportedUser] >= reportThreshold) {
            isBlocked[reportedUser] = true;
            emit UserBlocked(reportedUser);
        }
    }

    function unblockUser(address user) external onlyOwner {
        require(isBlocked[user], "User is not blocked");
        isBlocked[user] = false;
        reportCount[user] = 0;
        emit UserUnblocked(user);
    }

    function payReward(address user) external onlyOwner {
        require(!isBlocked[user], "User is blocked");
        require(token.balanceOf(address(this)) >= rewardAmount, "Insufficient token balance");
        
        token.transfer(user, rewardAmount);
        emit RewardPaid(user, rewardAmount);
    }

    function setRewardAmount(uint256 _amount) external onlyOwner {
        rewardAmount = _amount;
    }

    function setReportThreshold(uint256 _threshold) external onlyOwner {
        reportThreshold = _threshold;
    }

    function setCooldownPeriod(uint256 _period) external onlyOwner {
        cooldownPeriod = _period;
    }
} 