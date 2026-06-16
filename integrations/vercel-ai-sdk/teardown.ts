import { testConfig } from './config/test-config';

export default async function () {
  console.log("Running global teardown...");
  try {
    await testConfig.fetchDeleteId();
    await testConfig.deleteUser();
    console.log("User deleted successfully after all tests.");
  } catch (error) {
    console.error("Failed to delete user after all tests:", error);
  }
}