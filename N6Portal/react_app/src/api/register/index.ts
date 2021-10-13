import { controllers, customAxios, dataController } from 'api';

export const postRegister = async (data: FormData): Promise<void> => {
  try {
    await customAxios.post(`${dataController}${controllers.register.registerEndpoint}`, data);
  } catch (reason) {
    throw reason;
  }
};
