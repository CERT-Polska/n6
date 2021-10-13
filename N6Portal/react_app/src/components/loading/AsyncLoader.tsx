import { lazy, ComponentType, LazyExoticComponent } from 'react';

const AsyncLoader = <T extends unknown>(
  getComponent: () => Promise<{ default: ComponentType<T> }>
): LazyExoticComponent<ComponentType<T>> => lazy(getComponent);

export default AsyncLoader;
