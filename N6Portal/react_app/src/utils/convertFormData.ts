export const convertArrayToString = (arr: Record<'value', string>[]): string => arr.map((item) => item.value).join();
export const convertArrayToStringWithoutEmptyValues = (arr: Record<'value', string>[]): string => {
  return arr
    .filter((item) => !!item.value && item.value !== '__:__') // '__:__' is the empty TimeInput value
    .map((item) => item.value)
    .join();
};

export const convertArrayToArrayOfObjects = (
  arr: Array<number | string>,
  withDefaultValue?: boolean
): Record<'value', string>[] => {
  const arrayOfObjects = arr.map((item) => ({ value: `${item}` }));
  return withDefaultValue ? (arr.length > 0 ? arrayOfObjects : [{ value: '' }]) : arrayOfObjects;
};
