export const availableResources = {
  search: '/search/events',
  threats: '/report/threats',
  inside: '/report/inside'
} as const;

export type AvailableResource = (typeof availableResources)[keyof typeof availableResources][];

interface IMockedUser {
  login: string;
  password: string;
  availableResources: AvailableResource;
}

export const mockedValidUserAccount = {
  login: 'user@example.com',
  password: 'password'
};

export const mockedNoMfaUserAccount = {
  login: 'user_no_mfa@example.com',
  password: 'password'
};

export class MockedUser implements IMockedUser {
  readonly login: string;
  readonly password: string;
  readonly availableResources: AvailableResource;
  readonly name: string;
  readonly knowledgeBaseEnabled: boolean;
  readonly fullAccess: boolean;
  readonly api_key_auth_enabled: boolean;

  constructor(
    availableResources: AvailableResource,
    name: string,
    knowledgeBaseEnabled = true,
    fullAccess = true,
    api_key_auth_enabled = true,
    login: string = mockedValidUserAccount.login,
    password: string = mockedValidUserAccount.password
  ) {
    this.login = login;
    this.password = password;
    this.availableResources = availableResources;
    this.name = name;
    this.knowledgeBaseEnabled = knowledgeBaseEnabled;
    this.fullAccess = fullAccess;
    this.api_key_auth_enabled = api_key_auth_enabled;
  }
}

export const userWithSearchResource = new MockedUser([availableResources.search], 'UserWithSearchResource');

export const userWithThreatsResource = new MockedUser([availableResources.threats], 'UserWithThreatsResource');

export const userWithInsideResource = new MockedUser([availableResources.inside], 'UserWithInsideResource');

export const userWithSearchAndThreatsResource = new MockedUser(
  [availableResources.threats, availableResources.search],
  'UserWithSearchAndThreatsResource'
);

export const userWithSearchAndInsideResource = new MockedUser(
  [availableResources.inside, availableResources.search],
  'UserWithSearchAndInsideResource'
);

export const userWithThreatsAndInsideResource = new MockedUser(
  [availableResources.inside, availableResources.threats],
  'UserWithThreatsAndInsideResource'
);

export const userWithAllResources = new MockedUser(
  [availableResources.inside, availableResources.threats, availableResources.search],
  'UserWithAllResources'
);

export const userWithNoResources = new MockedUser([], 'UserWithNoResources');

export const userWithNoAdditionalAccess = new MockedUser(
  [availableResources.inside, availableResources.threats, availableResources.search],
  'UserWithNonFullAccessAndKnowledgeBaseDisabled',
  false,
  false,
  false
);

export const listOfUsers = [
  userWithAllResources,
  userWithSearchAndInsideResource,
  userWithSearchAndThreatsResource,
  userWithThreatsAndInsideResource,
  userWithSearchResource,
  userWithThreatsResource,
  userWithInsideResource,
  userWithNoResources,
  userWithNoAdditionalAccess
];
