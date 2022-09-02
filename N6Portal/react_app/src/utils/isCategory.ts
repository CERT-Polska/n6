import { categories } from 'api/services/barChart/types';
import { TCategory } from 'api/services/globalTypes';

export const isCategory = (value: string): value is TCategory => categories.some((category) => value === category);
