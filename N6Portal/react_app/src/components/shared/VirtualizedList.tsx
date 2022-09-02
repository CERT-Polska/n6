import { ComponentType, FC, useRef } from 'react';
import AutoSizer from 'react-virtualized-auto-sizer';
import { ListChildComponentProps, VariableSizeList } from 'react-window';

interface IProps {
  itemCount: number;
  height: number;
  className?: string;
  itemSize: (index: number) => number | number;
  children: ComponentType<ListChildComponentProps>;
}

const VirtualizedList: FC<IProps> = ({ itemCount, height, className, itemSize, children }) => {
  const listRef = useRef<VariableSizeList>(null);
  listRef.current?.resetAfterIndex(0);

  return (
    <AutoSizer disableHeight>
      {({ width }) => (
        <VariableSizeList
          ref={listRef}
          height={height}
          itemCount={itemCount}
          itemSize={itemSize}
          width={width}
          className={className}
        >
          {children}
        </VariableSizeList>
      )}
    </AutoSizer>
  );
};

export default VirtualizedList;
