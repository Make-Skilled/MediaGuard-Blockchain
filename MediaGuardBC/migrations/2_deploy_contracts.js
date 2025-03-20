const MediaGuardToken = artifacts.require("MediaGuardToken");
const MediaGuard = artifacts.require("MediaGuard");

module.exports = async function(deployer) {
  // Deploy the token contract first
  await deployer.deploy(MediaGuardToken);
  const token = await MediaGuardToken.deployed();

  // Deploy the main contract with the token address
  await deployer.deploy(MediaGuard, token.address);
}; 