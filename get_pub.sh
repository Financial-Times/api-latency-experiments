# Grab publication times from a log file

# ssh $EXP_SSH zgrep \'com.ft.methode.publication.STATS\' $EXP_LOG-20150704.gz > pub.log.1-20150704
ssh $EXP_SSH grep \'com.ft.methode.publication.STATS\' $EXP_LOG > pub.log

