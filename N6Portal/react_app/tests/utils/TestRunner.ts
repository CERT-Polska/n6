import test, { Page } from '@playwright/test';
import { MockedUser } from './mockedUsers';

export const runTestsForEachUser = (
  testName: string,
  users: MockedUser[],
  beforeEach: (page: Page, user: MockedUser) => Promise<void>,
  tests: (user: MockedUser) => void
) => {
  test.describe(testName, () => {
    users.forEach((user) => {
      test.describe(user.name, () => {
        test.beforeEach(async ({ page }) => {
          await beforeEach(page, user);
        });
        tests(user);
      });
    });
  });
};

export class TestRunnerBuilder {
  private testName: string;
  private users: MockedUser[];
  private beforeEachFn: (page: Page, user: MockedUser) => Promise<void>;
  private testsFn: (user: MockedUser) => void;

  withTestName(testName: string): TestRunnerBuilder {
    this.testName = testName;
    return this;
  }

  withUsers(users: MockedUser[]): TestRunnerBuilder {
    this.users = users;
    return this;
  }

  withBeforeEach(beforeEach: (page: Page, user: MockedUser) => Promise<void>): TestRunnerBuilder {
    this.beforeEachFn = beforeEach;
    return this;
  }

  withTests(tests: (user: MockedUser) => void): TestRunnerBuilder {
    this.testsFn = tests;
    return this;
  }

  build(): TestRunner {
    if (!this.testName || !this.users || !this.beforeEachFn || !this.testsFn) {
      throw new Error('All properties must be set before building TestRunner');
    }
    return new TestRunner(this.testName, this.users, this.beforeEachFn, this.testsFn);
  }
}

export class TestRunner {
  constructor(
    private readonly testName: string,
    private readonly users: MockedUser[],
    private readonly beforeEach: (page: Page, user: MockedUser) => Promise<void>,
    private readonly tests: (user: MockedUser) => void
  ) {}

  runTests(): void {
    runTestsForEachUser(this.testName, this.users, this.beforeEach, this.tests);
  }

  static get builder(): TestRunnerBuilder {
    return new TestRunnerBuilder();
  }
}
