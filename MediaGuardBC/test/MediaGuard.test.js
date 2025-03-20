const MediaGuardToken = artifacts.require("MediaGuardToken");
const MediaGuard = artifacts.require("MediaGuard");

contract("MediaGuard", accounts => {
  let token;
  let mediaGuard;
  const owner = accounts[0];
  const user1 = accounts[1];
  const user2 = accounts[2];

  beforeEach(async () => {
    token = await MediaGuardToken.new();
    mediaGuard = await MediaGuard.new(token.address);
  });

  describe("User Registration", () => {
    it("should allow users to register", async () => {
      await mediaGuard.register({ from: user1 });
      const user = await mediaGuard.getUser(user1);
      assert(user.isRegistered, "User should be registered");
    });

    it("should not allow duplicate registration", async () => {
      await mediaGuard.register({ from: user1 });
      try {
        await mediaGuard.register({ from: user1 });
        assert.fail("Should have thrown an error");
      } catch (err) {
        assert.include(err.message, "User already registered");
      }
    });
  });

  describe("Post Creation", () => {
    beforeEach(async () => {
      await mediaGuard.register({ from: user1 });
    });

    it("should allow registered users to create posts", async () => {
      const result = await mediaGuard.createPost("QmTest", 30, { from: user1 });
      const post = await mediaGuard.getPost(0);
      assert.equal(post.author, user1);
      assert.equal(post.contentHash, "QmTest");
      assert.equal(post.vulgarityScore, 30);
      assert(!post.isBlocked);
    });

    it("should block posts with high vulgarity scores", async () => {
      await mediaGuard.createPost("QmTest", 60, { from: user1 });
      const post = await mediaGuard.getPost(0);
      assert(post.isBlocked);
    });

    it("should not allow blocked users to create posts", async () => {
      // Create 3 posts with high vulgarity to get blocked
      for (let i = 0; i < 3; i++) {
        await mediaGuard.createPost("QmTest", 60, { from: user1 });
      }
      
      try {
        await mediaGuard.createPost("QmTest", 30, { from: user1 });
        assert.fail("Should have thrown an error");
      } catch (err) {
        assert.include(err.message, "User is blocked");
      }
    });
  });

  describe("Unblock Request System", () => {
    beforeEach(async () => {
      await mediaGuard.register({ from: user1 });
      // Block the user
      for (let i = 0; i < 3; i++) {
        await mediaGuard.createPost("QmTest", 60, { from: user1 });
      }
    });

    it("should allow blocked users to request unblock", async () => {
      await mediaGuard.requestUnblock({ from: user1 });
      const user = await mediaGuard.getUser(user1);
      assert(user.hasUnblockRequest);
    });

    it("should not allow non-blocked users to request unblock", async () => {
      await mediaGuard.register({ from: user2 });
      try {
        await mediaGuard.requestUnblock({ from: user2 });
        assert.fail("Should have thrown an error");
      } catch (err) {
        assert.include(err.message, "User is not blocked");
      }
    });

    it("should allow owner to analyze and unblock users", async () => {
      await mediaGuard.requestUnblock({ from: user1 });
      await mediaGuard.analyzeAndUnblockUser(user1, { from: owner });
      const user = await mediaGuard.getUser(user1);
      assert(!user.isBlocked);
      assert.equal(user.violationCount, 0);
      assert(!user.hasUnblockRequest);
    });
  });
}); 