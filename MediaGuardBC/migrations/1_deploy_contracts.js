const MediaGuardToken = artifacts.require("MediaGuardToken");
const MediaGuard = artifacts.require("MediaGuard");

module.exports = async function(deployer, network, accounts) {
  try {
    // Deploy MediaGuardToken first
    console.log('Deploying MediaGuardToken...');
    await deployer.deploy(MediaGuardToken, { from: accounts[0] });
    const tokenInstance = await MediaGuardToken.deployed();
    console.log('MediaGuardToken deployed at:', tokenInstance.address);

    // Deploy MediaGuard with the token's address
    console.log('Deploying MediaGuard...');
    await deployer.deploy(MediaGuard, tokenInstance.address, { from: accounts[0] });
    const guardInstance = await MediaGuard.deployed();
    console.log('MediaGuard deployed at:', guardInstance.address);
  } catch (error) {
    console.error('Error during deployment:', error);
    throw error;
  }
}; 