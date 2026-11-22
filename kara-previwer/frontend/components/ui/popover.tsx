import * as P from "@radix-ui/react-popover";
export const Popover = P.Root,
  PopoverTrigger = P.Trigger;
export const PopoverContent = (props) => (
  <P.Portal>
    <P.Content sideOffset={6} {...props} />
  </P.Portal>
);
