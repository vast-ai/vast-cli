#!/usr/bin/env bash

# This little utility notices when the timestamps change in this directory
# and then reruns the pdf generator script. If you have something like
# evince running that reloads the PDF when it changes this can be very
# convenient.

while true
do
  watch -g ls -l *.py *.sh *.png *.pdf; echo "Something changed. Sleeping 1..."; sleep 1; vastai generate pdf-invoices
done