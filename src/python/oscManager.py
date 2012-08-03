# using pyliblo (python wrapper of liblo)
# For examples of usage see:
# http://das.nasophon.de/pyliblo/examples.html

import liblo
import sys
import threading
import common

class OSCManager(threading.Thread):

  # OSC server
  server = liblo.Server()
  
  common = common.CommonData()
  
  # constructor
  def __init__(self, port=8888):
    # create server, listening on port 8888 by default
    try:
      self.server = liblo.Server(port)
    except liblo.ServerError, err:
      print str(err)
      sys.exit()
      
    # register callback to register/unregister OSC clients (computers that will receive 
    # the messages when a new tweet arrives
    self.server.add_method("/twt/register", 's', twt_register_callback)
    self.server.add_method("/twt/unregister", 's', twt_unregister_callback)

    # OSC messages to dynamically controll params
    self.server.add_method("/twt/thresholdUp", '', twt_threshold_up_callback)
    self.server.add_method("/twt/thresholdDown", '', twt_threshold_down_callback)
    self.server.add_method("/twt/delayUp", '', twt_delay_up_callback)
    self.server.add_method("/twt/delayDown", '', twt_delay_down_callback)
    self.server.add_method("/twt/keyword", 's', twt_keyword_callback)
    self.server.add_method("/twt/addTerm", 's', twt_add_search_term_callback)
    self.server.add_method("/twt/removeTerm", 's', twt_remove_search_term_callback)
    self.server.add_method("/twt/startsearching", '', twt_start_searching_callback)
    self.server.add_method("/twt/disconnect", '', twt_disconnect_callback)
    self.server.add_method("/twt/dequeueTime", 'ffi', twt_update_tweet_dequeue_time_callback)
    self.server.add_method("/twt/treeThresh", 'f', twt_update_cosine_threshold_callback)


    # register a fallback for unhandled messages
    self.server.add_method(None, None, fallback)
    
    self.running = False
    
    # call the thread initializer
    threading.Thread.__init__(self)


  def run(self):
    print "Starting OSC listener\n"
    self.running = True
    while self.running:
      #check for messages every 100 ms
      self.server.recv(100)
    
      
  def register_callback(self, message, types, callback, data = None):
    if data == None:
      # register method without passing user data to the callback
      self.server.add_method(message, types, callback)
    else:
      # register method passing user data to the callback
      self.server.add_method(message, types, callback, data)      
      
#/twt/newNode, id, closest_neighbord, distance (0-1), twt_text, [i i f s]
  def sendNewNode(self, port, msgArgs, msgTypes):
    msg = liblo.Message("/twt/newNode")
    for a, t in zip(msgArgs, msgTypes):
      msg.add((t, a))
      #print "argument (%s): %s" % (t, a)
    for client in self.common.clients:
      try:
        target = liblo.Address(client, port)
      except:
        print str(err)
        #sys.exit()
      #print "/twt/newNode", "(node_id:", msgArgs[0], "closest_id:", msgArgs[1], "distance:", msgArgs[2], "tweet:", msgArgs[3][:20], "...)"
      #print target, msg
      liblo.send(target, msg)



#/twt/triggerNode echo_id, node_id, time, hop_level, [i i f i]      
# TODO: use and test. node_delay is a map where the node_id is the key 
#       and the delay is the value (e.g. node_delay = {43:500, 67:4000, 87:2300} )
# TODO: replace the 1.0 with the actual hop-level (ask Luke about it)
  def triggerNodes(self, port, echo_id, node_delay, hop_level):
    msg = liblo.Message("/twt/triggerNode")
    for key in node_delay:
      value = node_delay[key]
      for a, t in zip((echo_id, key, value, hop_level), ('i', 's', 'f', 'i')):
        msg.add((t, a))
        #print "argument (%s): %s" % (t, a)
      for client in self.common.clients:
        try:
          target = liblo.Address(client, port)
        except:
          print str(err)
          #sys.exit()
        #print "Sending triggerNode message to", client, "(echo_id:", echo_id, "node_id:", key, "time:", value, "hop_level:", hop_level, ")"
        #print "/twt/triggerNode", "(echo_id:", echo_id, "node_id:", key, "time:", value, "hop_level:", hop_level, ")"

        liblo.send(target, msg)


      
      
common = common.CommonData()

# Callbacks (need to be defined outside the class)

def fallback(path, args, types, src):
  print "got unknown message '%s' from '%s'" % (path, src.get_url())
  for a, t in zip(args, types):
    print "argument of type '%s': %s" % (t, a)


def twt_register_callback(path, args):
  global common
  ip_str = args[0]
  common.register(ip_str)
  common.showClients()

    
def twt_unregister_callback(path, args):
  global common
  ip_str = args[0]
  common.unregister(ip_str)
  common.showClients()


def twt_threshold_up_callback(path, args):
  global common
  common.triggerLengthThreshold += 1
  print "*** Changing threshold up: ", common.triggerLengthThreshold


def twt_threshold_down_callback(path, args):
  global common
  if common.triggerLengthThreshold > 3:
    common.triggerLengthThreshold -= 1
    print "*** Changing threshold down: ", common.triggerLengthThreshold
  else:
    print "*** Lower limit reached. Threshold not changed\n"


def twt_delay_up_callback(path, args):
  global common
  common.initial_delay += 500
  print "*** Changing delay up: ", common.initial_delay


def twt_delay_down_callback(path, args):
  global common
  if common.initial_delay > 500:
    common.initial_delay -= 500
    print "*** Changing delay down: ", common.initial_delay
  else:
    print "*** Lower limit reached. Delay not changed\n"

  
def twt_start_searching_callback(path, args):
  global common
  common.waitingForChuck = False
  common.waitingForProcessing = False


def twt_disconnect_callback(path, args):
  global common
  print 20*"O", "Closing connection"
  common.connection = False


def twt_add_search_term_callback(path, args):
  global common
  print "Adding '", args[0], "' to the search terms set"
  if args[0] not in common.search_terms:
    common.search_terms.add(args[0])
    common.connection = False
    common.newTweetsQueue.clear()
    #send_search_term(args[0])


def twt_remove_search_term_callback(path, args):
  global common
  print "Removing '", args[0], "' from the search terms set"
  if args[0] in common.search_terms:
    common.search_terms.remove(args[0])
    common.connection = False
    common.newTweetsQueue.clear()
    #send_search_term(args[0], True)


def twt_update_tweet_dequeue_time_callback(path, args):
  global common
  if args[2] == 0:
    common.keyword_dispatcher.low = args[0]
    common.keyword_dispatcher.high = args[1]
    if common.keyword_dispatcher.low < common.lower_dequeuing_limit:
      common.keyword_dispatcher.low = common.lower_dequeuing_limit
    if common.keyword_dispatcher.high < common.keyword_dispatcher.low: 
      common.keyword_dispatcher.high = common.keyword_dispatcher.low
    print "changing local dequeing times %.2f, %.2f" % (common.keyword_dispatcher.low,   common.keyword_dispatcher.high, )
  else:
    common.general_dispatcher.low = args[0]
    common.general_dispatcher.high = args[1]
    if common.general_dispatcher.low < common.lower_dequeuing_limit:
      common.general_dispatcher.low = common.lower_dequeuing_limit
    if common.general_dispatcher.high < common.general_dispatcher.low: 
      common.general_dispatcher.high = common.general_dispatcher.low
    print "changing global dequeing times %.2f, %.2f" % (common.general_dispatcher.low, common.general_dispatcher.high, )
  #print "new dequeuing time limits: ", args[0], " - ", args[1]


def twt_update_cosine_threshold_callback(path, args):
  global common
  common.cosine_threshold = args[0]
  print "New cosine distance threshold = %.2f" % (common.cosine_threshold,)

def twt_keyword_callback(path, args):
  global common
  print "Adding '", args[0], "' to the keyword list"
  if args[0] not in common.keywords:
    common.keywords.add(args[0])
    common.connection = False

def send_keyword_term(term, port=8891):
  global common
  msg = liblo.Message("/twt/keyword")
  for a, t in zip((term,), ('s',)):
    msg.add((t, a))
    #print "argument (%s): %s" % (t, a)
  for client in common.clients:
    try:
      target = liblo.Address(client, port)
    except:
      print str(err)
    liblo.send(target, msg)
  
  
  
def send_search_term(term, remove=False, port=8891):
  global common
  msg = liblo.Message("/twt/newsearchTerm")
  if remove: msg = liblo.Message("/twt/removesearchTerm")
  for a, t in zip((term,), ('s',)):
    msg.add((t, a))
    #print "argument (%s): %s" % (t, a)
  for client in common.clients:
    try:
      target = liblo.Address(client, port)
    except:
      print str(err)
    liblo.send(target, msg)
  