/**
 * @jest-environment jsdom
 */
// jest environment to allow mocking of document.createElement

import { getScrollbarWidth } from './getScrollbarWidth';

describe('getScrollbarWidth', () => {
  afterAll(() => {
    jest.clearAllMocks();
  });

  it('calculates right padding for Table components using default div "hidden scroll" className', () => {
    const mockElement = document.createElement('div');
    Object.defineProperty(mockElement, 'offsetWidth', { value: 50, configurable: true });
    Object.defineProperty(mockElement, 'clientWidth', { value: 30, configurable: true });
    const createElementSpy = jest.spyOn(document, 'createElement');
    createElementSpy.mockReturnValue(mockElement);
    expect(getScrollbarWidth()).toBe('20px');
    mockElement.parentNode?.removeChild(mockElement);
  });

  it('calculates right padding for Table components even if parentNode is undefined', () => {
    const mockElement = document.createElement('div');
    Object.defineProperty(mockElement, 'offsetWidth', { value: 50, configurable: true });
    Object.defineProperty(mockElement, 'clientWidth', { value: 30, configurable: true });
    Object.defineProperty(mockElement, 'parentNode', { value: undefined });
    const createElementSpy = jest.spyOn(document, 'createElement');
    createElementSpy.mockReturnValue(mockElement);
    expect(getScrollbarWidth()).toBe('20px');
  });

  it('returns 0px when theres no border-padding gap', () => {
    const mockElement = document.createElement('div');
    Object.defineProperty(mockElement, 'offsetWidth', { value: 50, configurable: true });
    Object.defineProperty(mockElement, 'clientWidth', { value: 50, configurable: true });
    const createElementSpy = jest.spyOn(document, 'createElement');
    createElementSpy.mockReturnValue(mockElement);
    expect(getScrollbarWidth()).toBe('0px');
    mockElement.parentNode?.removeChild(mockElement);
  });
});
