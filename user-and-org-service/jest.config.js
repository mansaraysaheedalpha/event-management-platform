module.exports = {
  moduleFileExtensions: ['js', 'json', 'ts'],
  rootDir: 'src',
  testRegex: '.*\\.spec\\.ts$',
  transform: {
    '^.+\\.(t|j)s$': 'ts-jest',
  },
  collectCoverageFrom: ['**/*.(t|j)s'],
  coverageDirectory: '../coverage',
  testEnvironment: 'node',
  // This part fixes the 'Cannot find module' errors
  moduleNameMapper: {
    '^src/(.*)$': '<rootDir>/$1',
  },
  // This line ensures your .env file is loaded for tests
  setupFiles: ['dotenv/config'],
};