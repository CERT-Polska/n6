/**
 * @jest-environment jsdom
 */

import { postRegister } from './index';
import { waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('postRegister', () => {
  it('calls /register POST method, without returning any value', async () => {
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: { test: 'data' } }));
    const payloadData: Promise<void> = postRegister({} as FormData);
    waitFor(() => {
      expect(payloadData).resolves.not.toBe(null);
    });
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.register.registerEndpoint}`, {});
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<void> = postRegister({} as FormData);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});
