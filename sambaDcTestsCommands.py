import paramiko
import os
import commands
import subprocess
import time
import collections
import random
import string
from random import randint
NOT_FOUND=-1

class sambaDcTestsCommands:
    #local channel used to run commands
    channel=None
    sshclient=None

    def __init__ (self):
        pass

    def sshConnect (self, sshkey, hostip, sshport, user):
        """ Create a SSH connection """
        clone=self
        #print ('try to connect to host')
        try:

            clone.sshclient = paramiko.SSHClient()
            #override check in known hosts file
            #https://github.com/paramiko/paramiko/issues/340
            clone.sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            clone.sshclient.connect( hostname = hostip, port = sshport, username = user, pkey = paramiko.RSAKey.from_private_key_file(sshkey))
            clone.channel = clone.sshclient.invoke_shell()

        except:
            #print ('cannot connect to host')
            return False

        #print('connected to ' + hostip)
    
    #Logins test
    
    def testLoginChangeHostName (self):
        """ Change the hostname  """
        self.exe ('sudo hostnamectl set-hostname "TEST-DC-' +  str(randint(0,99999)) + '" --static')

    
    
    def testLoginRealmJoin (self, domain, user, userPass):
        """ Join the host to the Domain Controller """ 
        try:
            self.testLoginChangeHostName()
            command='sudo realm join ' + domain + ' -U '+user
            self.exe(command)
            self.exe(userPass)
            time.sleep(20)
            return (self.testLoginRealmCheck(domain) == True)
        except ValueError as err:
            print(err.args)   

    def testLoginRealmCheck (self, domain):
        """ Check if the join worked.  """
        try:
            self.testLoginChangeHostName
            command='realm list'
            return (self.exe(command).find('domain-name: '+domain)!=NOT_FOUND)
        except ValueError as err:
            print(err.args)   
    
    def testLoginRealmLeave (self, domain):
        """ Unjoin the domain"""
        try:
            command='sudo realm leave'
            self.exe(command)
            time.sleep(5)
            return (self.testLoginRealmCheck(domain) == False)
        except ValueError as err:
            print(err.args)   
    
    #Kerberos
    
    def testLoginKerberos (self, user, domain, userPass):
        """ Login using Kerberos - kinit"""
        try:
            command='kinit ' +user
            self.exe(command)
            self.exe(userPass)
            return self.testLoginCheckKerberos(user, domain)
        except ValueError as err:
            print(err.args)   

    def testLoginCheckKerberos (self, user, domain):
        """ Check if kerberos is Ok """
        return (self.exe('klist').find('Default principal: '+user+'@'+domain.upper())!=NOT_FOUND)
   
    def testLoginDestroyKerberos (self, user, domain):
        """ Destroy kerberos session """
        if self.testLoginCheckKerberos(user, domain):
            self.exe('kdestroy -A')
            return (not (self.testLoginCheckKerberos(user, domain)))
        else:
            return True

    
    #SMBClient

    def testLoginSmbClient (self, user, domain, userPass):
        """ Try to login using SMB Client """
        try:
            if not self.testLoginCheckKerberos(user, domain):
                self.testLoginKerberos(user, domain, userPass)    
            command='smbclient -U '+user+' -L' +domain
            self.exe(command)
            verbose = self.exe(userPass)
            #self.sshclient.close()
            return (verbose.find('Domain=[UBEE]')!=NOT_FOUND)                                  
        except ValueError as err:
            print(err.args)  
    
    #DNS 

    #LDAP Entry
    def testDNSLDAPEntry (self, domain, dcs=[]):
        """ Look for LDAP DNS Entry"""
        v = (self.exe ('host -t SRV _ldap._tcp.'+domain+'.'))
        r = []
        for x in dcs:
            if x in v:
                r.append(True)
            else: 
                r.append(False)
        #self.sshclient.close()
        return all(r)


    #Kerberos Entry
    def testDNSKerberosEntry (self, domain, dcs=[]):
        """ Look for kerberos DNS Entry """
        v = (self.exe ('host -t SRV _kerberos._udp.'+domain+'.'))
        r = []
        for x in dcs:
            if x in v:
                r.append(True)
            else: 
                r.append(False)
        #self.sshclient.close()
        return all(r)

    #A Entry
    def testDNSAEntry (self, domain, dcs=[]):
        """ Look for A DNS Entrys """
        r = []
        for x in dcs:
            v = (self.exe ('host -t A '+x+'.'+domain+'.'))
            if (v.find(x+'.'+domain+' has address')!=NOT_FOUND):
                r.append(True)
            else: 
                r.append(False)
        #self.sshclient.close()
        return all(r)

    #NSLOOKUP Internal
    def testDNSLookupInternal (self, domain, ips_dcs=[]):
        """ Try to resolve internal DNS """
        r = []
        for x in ips_dcs:
            v = (self.exe('nslookup '+domain+' '+x))
            for y in ips_dcs:
                if y in v:
                    r.append(True)
                else:
                    r.append(False)
        #self.sshclient.close()
        return all(r)

        
    #NSLOOKUP External
    def testDNSLookupExternal (self, domainExternal, ips_dcs=[]):
        """ Try to resolve external DNS """
        r = []
        for x in ips_dcs:
            v = (self.exe('nslookup '+domainExternal+' '+x))
            for y in ips_dcs:
                if ((v.find('Name:')!=NOT_FOUND) and (v.find('Address:')!=NOT_FOUND)):
                    r.append(True)
                else:
                    r.append(False)
        #self.sshclient.close()
        return all(r)  

    #Check if samba is running
    def checkSambaIsOn (self, sshkey, sshport, user, ips_dcs=[]):
        """ Check if samba is running """
        r = []
        for x in ips_dcs:
            self.sshConnect(sshkey,x,sshport,user)
            v = (self.exe('systemctl status samba'))
            if (v.find('active (running)')!=NOT_FOUND):
                r.append(True)
            else:
                r.append(False)
        #self.sshclient.close()
        return all(r)
        
    #Replication
    def checkUsersList (self, sshkey, sshport, user, ips_dcs=[]):
        """ Check if all DCs have the same list of users """
        listOfLists, listOfResults = [],[]
        try:
            for ip in ips_dcs:
                self.sshConnect(sshkey,ip,sshport,user)
                command = ('sudo /usr/local/samba/bin/samba-tool user list')
                output = ((self.exe(command)))
                users = (output.splitlines()[:-1])
                while users[0].find('$')==NOT_FOUND:
                    del users[0]
                del users[0]
                listOfLists.append(users)
            for x in range(0, len(listOfLists)-1):
                listOfResults.append((lambda a, b: collections.Counter(a) == collections.Counter(b))(listOfLists[0],listOfLists[x+1]))
            self.sshclient.close()
            return all(listOfResults)
        except:
            return False

              
    def checkGroupList (self, sshkey, sshport, user, ips_dcs=[]):
        """ Check if all DCs have the same list of groups"""
        listOfLists, listOfResults = [],[]
        try:
            for ip in ips_dcs:
                self.sshConnect(sshkey,ip,sshport,user)
                command = ('sudo /usr/local/samba/bin/samba-tool group list')
                output = ((self.exe(command)))
                groups = (output.splitlines()[:-1])
                while groups[0].find('$')==NOT_FOUND:
                    del groups[0]
                del groups[0]
                listOfLists.append(groups)
            for x in range(0, len(listOfLists)-1):
                listOfResults.append((lambda a, b: collections.Counter(a) == collections.Counter(b))(listOfLists[0],listOfLists[x+1]))
            self.sshclient.close()
            return all(listOfResults)
        except:
            return False

    def testCreateNewUser (self, sshkey, sshport, user, ips_dcs=[]):
        """ Create a new user and check if it was replicated to all DCs. Create one user per DC"""
        result = []
        try:
            for ip in ips_dcs:
                random_number = str(randint(0,99999))
                random_pass = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
                self.sshConnect(sshkey,ip,sshport,user)
                self.exe('sudo /usr/local/samba/bin/samba-tool user create test-user-'+random_number)
                self.exe(random_pass)
                self.exe(random_pass)
                if (self.exe('sudo /usr/local/samba/bin/samba-tool user list | grep test-user-'+random_number)):
                    self.sshclient.close()
                    time.sleep(10)
                    result.append( (self.checkUsersList(sshkey, sshport, user, ips_dcs)))
                else:
                    result.append(False)
            self.sshclient.close()
            return all (result)
        except:
            return False

    def testDeleteTestUser (self, sshkey, sshport, user, ip_dc):
        """ delete all test-users and check if it was really deleted  """
        users =[]
        try:
            self.sshConnect(sshkey,ip_dc,sshport,user)
            output = self.exe('sudo /usr/local/samba/bin/samba-tool user list | grep --color=never test-user-')
            if (output.find('test-user-')!=NOT_FOUND):
                users = (output.splitlines()[:-1])
                while users[0].find('$')==NOT_FOUND:
                    del users[0]
                del users[0]
            for x in users:
                self.exe('sudo /usr/local/samba/bin/samba-tool user delete '+x)
            #self.sshclient.close()
            return not (self.exe ('sudo /usr/local/samba/bin/samba-tool user list | grep test-user-')==NOT_FOUND)
        except:
            return False

#    def checkGroupMembers (self, sshkey, sshport, user, ips_dcs=[]):
        """ Check for groups inconsistencys """
#       listOfLists, results, users = [],[],[]
#        self.sshConnect(sshkey,ips_dcs[randint(0,2)],sshport,user)
#        command = ('sudo /usr/local/samba/bin/samba-tool group list')
#        output = ((self.exe(command)))
#        groups = (output.splitlines()[:-1])
#        while groups[0].find('$')==NOT_FOUND:
#            del groups[0]
#        del groups[0]
#        self.sshclient.close()
#        for group in groups:
#            for ip in ips_dcs:
#                self.sshConnect(sshkey,ip,sshport,user)
#                output = (self.exe('sudo /usr/local/samba/bin/samba-tool group listmembers '+group))
#                users = (output.splitlines()[:-1])
#                while users[0].find('$')==NOT_FOUND:
#                    del users[0]
#                del users[0]   
#                listOfLists.append (users)
#            for x in range(0, len(listOfLists)-1):
#                print listOfLists[x]
#                results.append((lambda a, b: collections.Counter(a) == collections.Counter(b))(listOfLists[0],listOfLists[x+1]))
#        self.sshclient.close()
        #print (groups)
        #print (results)
#        return all (results)



    def changeUserPassword (self, sshkey, sshport, user, ip_dc, userPass, dcUser):
        """ Change the test user password. """
        self.sshConnect(sshkey,ip_dc,sshport,user)
        self.exe('sudo /usr/local/samba/bin/samba-tool user setpassword '+dcUser)
        self.exe(userPass)
        self.exe(userPass)
        self.sshclient.close()
    
    def disableAccount (self, sshkey, sshport, user, ip_dc, dcUser):
        """ Disable test account """
        self.sshConnect(sshkey,ip_dc,sshport,user)
        self.exe('sudo /usr/local/samba/bin/samba-tool user disable '+dcUser)
        self.sshclient.close()

    def enableAccount (self, sshkey, sshport, user, ip_dc, dcUser):
        """ Enable test account """
        self.sshConnect(sshkey,ip_dc,sshport,user)
        self.exe('sudo /usr/local/samba/bin/samba-tool user enable '+dcUser)
        self.sshclient.close()

    def createRandomPass (self):
        randomPass = (''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)]))
        return randomPass

    def closeSSHConnect (self):
        self.sshclient.close()
    
    def exe(self, command, printoutput=False):
        #print  commands.getoutput('uname -a')
        buff_size=4096
        c=command + '\n'
        #print c
        self.channel.send(c)
        time.sleep(1) 


        #print results 
        while self.channel.recv_ready():
            output=self.channel.recv(buff_size)
            if printoutput==True:
                print(output)

        return output

