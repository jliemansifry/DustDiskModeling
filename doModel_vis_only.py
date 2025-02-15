import triangle
from scipy.stats import mstats
import numpy as np
import emcee
from visgen_master import VisibilityGenerator
from disk_spl import Disk
from astropy.io import fits
import os
import time 
from emcee.utils import MPIPool
import sys

blowoutSize = (3 * 4.04  * 3.8e26)/ (16 * 3.14159 * 2.7 * 6.67e-11 * 1.4 *1.988e33 * 2.9979e8)# 3 * stellar luminosity in solar luminosities * convert to watts / 16 pi * rho * G * mstar in stellar masses * convert to kg * c (in meters)

def define_start_and_run(): #called at the bottom
    pC = np.array([60, 50, -2, 0, 0]) # center positions for the gaussian ball for each parameter to be varied
    pW = np.array([20, 30, 0.5, 30, 30]) # gaussian widths for each parameter
    run_pool((pC),(pW),2,6) #20 walkers, 300 steps

def lnlike_visonly(p):
    if p[0] < 0.0001 or p[1] <= 0.10 or p[3] > 90 or p[3] < 0 or p[4] < -90 or p[4] > 90: # set up boundaries for naughty parameters. rIn can't be negative, delR can't be below 0.1 because that is the resolution of the model, inc can't be negative or greater than 90, and PA is the same after a 180deg rotation, so we limit it to -90<PA<90
        return -np.inf
    else:
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False)
        fits_file = 'fitsFile'+tf.name[-9:]
        
        disk = Disk(0.0001,p[0],p[1],10**p[2], 0, 0.8, blowoutSize*1e6, 1)
        #rawDiskChi = disk.computeChiSquared()
        visGen = VisibilityGenerator(1024,p[3],p[4],fits_file)
        rawVisChi = visGen.computeChiSquared(disk)
        os.system('rm -rf images/'+fits_file+'.fits')
        os.system('rm -rf images/'+fits_file+'.mp')
        os.system('rm -rf images/'+fits_file+'.vis')
        os.system('rm -rf images/'+fits_file+'2.vis')
        os.system('rm -rf images/'+fits_file+'3.vis')
        os.system('rm -rf images/'+fits_file+'.uvf')
        os.system('rm -rf images/'+fits_file+'2.uvf')
        os.system('rm -rf images/'+fits_file+'3.uvf')
        os.system('rm -rf fits/'+fits_file)
        if np.isnan(rawVisChi):
            return -np.inf
        return -(rawVisChi)/2.

def run_pool(pC, pW, walk, step): #pCenter and pWidths
    steps = step
    nwalkers = walk 
    ndim = len(pC)
    ## r in, del r, i, PA
    p0 = [pC[0], pC[1], pC[2],  pC[3], pC[4]]
    widths = [pW[0], pW[1], pW[2],  pW[3], pW[4]]
    p = emcee.utils.sample_ball(p0,widths,size=nwalkers)
    
    pool = MPIPool()
    if not pool.is_master():
        pool.wait()
        sys.exit(0)
    sampler = emcee.EnsembleSampler(nwalkers, ndim, lnlike_visonly, live_dangerously=True,  pool=pool)
    
    print 'Beginning the MCMC run.'
    start = time.clock()
    sampler.run_mcmc(p, steps)
    stop = time.clock()
    pool.close()
    print 'MCMC finished successfully.\n'
    print 'This was a visibility-only run with {} walkers and {} steps'.format(nwalkers,steps)
    print "Mean acor time: "+str(np.mean(sampler.acor))
    print "\nMean acceptance fraction: "+str(np.mean(sampler.acceptance_fraction))
    print 'Run took %r minutes' % ((stop - start)/60.)

    chain = sampler.chain
    chi = (sampler.lnprobability)/(-0.5)
    whatbywhat = str(nwalkers)+'x'+str(steps)
    os.system('mkdir MCMCRUNS/vis_only/'+whatbywhat)
    chainFile = 'MCMCRUNS/vis_only/'+whatbywhat+'/'+whatbywhat+'.chain.fits'
    chiFile = 'MCMCRUNS/vis_only/'+whatbywhat+'/'+whatbywhat+'.chi.fits'
    infoFile = 'MCMCRUNS/vis_only/'+whatbywhat+'/'+whatbywhat+'.runInfo.txt'
    fits.writeto(chainFile,chain)
    fits.writeto(chiFile,chi)
    f = open(infoFile,'w')
    f.write('run took %r minutes\n' % ((stop - start)/60.))
    f.write('walkers: %r\n' % nwalkers)
    f.write('steps: %r\n' % steps)
    f.write('initial model: %r\n' % p0)
    f.write('widths: %r\n' % widths)
    f.write("mean acor time: "+str(np.mean(sampler.acor)))
    f.write("\nmean acceptance fraction: "+str(np.mean(sampler.acceptance_fraction)))
    f.close()

    print 'Data written to: \n'+chainFile+'\n'+chiFile+'\n'+infoFile

define_start_and_run()
