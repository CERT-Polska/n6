export interface IRouteElem {
  readonly path: string;
  readonly component: React.FunctionComponentElement<React.LazyExoticComponent<React.ComponentType<React.FC>>>;
  readonly param?: string;
}
export interface IPrivateRouteElem extends IRouteElem {
  redirectPath: string;
}
