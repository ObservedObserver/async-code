import { Clock, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface TaskStatusBadgeProps {
    status: string;
    className?: string;
    iconOnly?: boolean;
}

export function TaskStatusBadge({ status, className, iconOnly = false }: TaskStatusBadgeProps) {
    const getStatusConfig = (status: string) => {
        switch (status) {
            case "pending":
                return {
                    icon: <Clock className="w-4 h-4" />,
                    text: "pending",
                    className: "bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200"
                };
            
            case "running":
                return {
                    icon: <AlertCircle className="w-4 h-4" />,
                    text: "running",
                    className: "bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-200"
                };
            
            case "completed":
                return {
                    icon: <CheckCircle className="w-4 h-4" />,
                    text: "completed",
                    className: "bg-green-100 text-green-700 border-green-200 hover:bg-green-200"
                };
            
            case "failed":
                return {
                    icon: <XCircle className="w-4 h-4" />,
                    text: "failed",
                    className: "bg-red-100 text-red-700 border-red-200 hover:bg-red-200"
                };
            
            default:
                return {
                    icon: null,
                    text: status,
                    className: "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200"
                };
        }
    };

    const config = getStatusConfig(status);

    if (iconOnly) {
        return (
            <Badge 
                variant="outline" 
                className={cn(
                    "gap-0 p-1.5 rounded-full border-2 transition-colors",
                    config.className,
                    className
                )}
                title={config.text}
            >
                {config.icon}
            </Badge>
        );
    }

    return (
        <Badge 
            variant="outline" 
            className={cn(
                "gap-1 transition-colors",
                config.className,
                className
            )}
        >
            {config.icon}
            {config.text}
        </Badge>
    );
}