import microcontroller
import supervisor

#supervisor.autoreload = False

print (supervisor.runtime.safe_mode_reason)

if supervisor.runtime.safe_mode_reason == supervisor.SafeModeReason.BROWNOUT:
    microcontroller.reset()

