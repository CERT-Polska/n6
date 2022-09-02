export interface IRouteElem {
  readonly path: string;
  readonly component: React.FunctionComponentElement<React.LazyExoticComponent<React.ComponentType<React.FC>>>;
  readonly param?: string;
  readonly exact?: boolean;
}
export interface IPrivateRouteElem extends IRouteElem {
  redirectPath: string;
}
